"""Offline backup engine (spec §26).

Backup = consistent database dump + media directory + manifest, packaged as a
single gzip'd tarball written to a local/attached/network destination folder.
No external or cloud service is involved.
"""

import hashlib
import json
import logging
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from .models import BackupJob, BackupKind, BackupProfile, BackupStatus

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = settings.BASE_DIR / "backups"


def _job_directory(job):
    """Folder the archive is written to; falls back to BACKUP_DIR/jobs."""
    profile = job.profile
    if profile and profile.destination_path:
        path = Path(profile.destination_path.strip())
        path.mkdir(parents=True, exist_ok=True)
        return path
    path = DEFAULT_BACKUP_DIR / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _db_engine():
    return connection.vendor


def _database_dump(tmp_dir):
    """Produce a consistent database backup inside tmp_dir.

    Returns the filename. SQLite uses the sqlite3 online backup API; Postgres
    uses ``pg_dump`` with a portable ``dumpdata`` JSON fallback.
    """
    if _db_engine() == "sqlite3":
        name = "db.sqlite3"
        target = tmp_dir / name
        source = connection.connection
        dest = sqlite3.connect(str(target))
        try:
            source.backup(dest)
        finally:
            dest.close()
        return name

    name = "edflow.dump"
    target = tmp_dir / name
    db = connection.settings_dict
    env = {}
    if db.get("PASSWORD"):
        env["PGPASSWORD"] = str(db["PASSWORD"])
    args = ["pg_dump", "--format=custom", "--no-owner", "-f", str(target), db["NAME"]]
    if db.get("HOST"):
        args += ["-h", str(db["HOST"])]
    if db.get("PORT"):
        args += ["-p", str(db["PORT"])]
    if db.get("USER"):
        args += ["-U", str(db["USER"])]
    try:
        subprocess.run(
            args, env=env, cwd=str(tmp_dir), check=True, capture_output=True,
            timeout=900,
        )
        return name
    except FileNotFoundError:
        # Portable fallback: full JSON dump via dumpdata.
        target = tmp_dir / "edflow.json"
        call_command("dumpdata", format="json", output=str(target),
                     exclude=["contenttypes", "auth.permission"])
        return "edflow.json"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(database_file, archive_name):
    return {
        "app": "EdFlow By AlgoriSync",
        "created": timezone.now().isoformat(),
        "database_file": database_file,
        "archive": archive_name,
        "engine": _db_engine(),
    }


def _count_entries():
    """Total number of persisted model rows for the manifest."""
    total = 0
    from django.apps import apps

    for model in apps.get_models():
        try:
            total += model.objects.count()
        except Exception:
            continue
    return total


def run_backup(profile, created_by=None, kind=BackupKind.MANUAL):
    """Create a backup for ``profile`` and record it as a BackupJob."""
    job = BackupJob.objects.create(
        profile=profile, created_by=created_by, kind=kind,
        started_at=timezone.now(),
    )
    try:
        destination = _job_directory(job)
        stamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"edflow_backup_{stamp}.tar.gz"
        archive_path = destination / archive_name

        with tempfile.TemporaryDirectory(prefix="edflow_backup_") as tmp:
            tmp_dir = Path(tmp)
            database_file = _database_dump(tmp_dir)

            media_source = Path(settings.MEDIA_ROOT)
            if media_source.exists():
                shutil.copytree(media_source, tmp_dir / "media", dirs_exist_ok=True)
            else:
                (tmp_dir / "media").mkdir()

            manifest = _manifest(database_file, archive_name)
            manifest["entries"] = _count_entries()
            (tmp_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            with tarfile.open(archive_path, "w:gz") as tar:
                for member in (database_file, "media", "manifest.json"):
                    tar.add(tmp_dir / member, arcname=member, recursive=True)

        size = archive_path.stat().st_size
        checksum = _sha256(archive_path)
        job.mark_success(
            archive_name=archive_name,
            archive_path=str(archive_path),
            archive_size=size,
            checksum=checksum,
            database_file=database_file,
            entries=manifest["entries"],
            note="Backup completed.",
        )
        _prune(profile)
        return job
    except Exception as exc:
        logger.exception("Backup failed for profile %s", profile)
        job.mark_failed(exc)
        return job


def verify_job(job):
    """Re-verify an existing archive: checksum + manifest + tarball integrity."""
    job.status = BackupStatus.VERIFYING
    job.save(update_fields=["status"])
    try:
        path = Path(job.archive_path)
        if not path.exists():
            raise FileNotFoundError("Archive file no longer exists on disk.")
        if _sha256(path) != job.checksum:
            raise ValueError("Checksum mismatch — archive was modified or corrupted.")
        with tarfile.open(path, "r:gz") as tar:
            names = tar.getnames()
            if job.database_file not in names:
                raise ValueError("Database dump is missing from archive.")
            if "manifest.json" not in names:
                raise ValueError("Manifest is missing from archive.")
            tar.extractfile("manifest.json").read()
        job.verified = True
        job.verified_at = timezone.now()
        job.status = BackupStatus.SUCCESS
        job.save(update_fields=["verified", "verified_at", "status"])
        return job
    except Exception as exc:
        job.status = BackupStatus.FAILED
        job.error = str(exc)[:4000]
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
        return job


def _prune(profile):
    """Apply retention: remove archives beyond ``profile.keep_count``."""
    keep = profile.keep_count if profile else 0
    if keep <= 0:
        return
    old_jobs = list(
        BackupJob.objects.filter(profile=profile)
        .order_by("-started_at")[keep:]
    )
    for job in old_jobs:
        if job.archive_path:
            try:
                Path(job.archive_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not delete archive %s", job.archive_path)
        job.delete()


def restore_backup(job, created_by=None):
    """Restore a backup.

    Always makes a pre-restore safety backup first. Extract happens into a temp
    directory with checksum verification before anything is touched.
    """
    if job.status != BackupStatus.SUCCESS:
        raise RuntimeError("Only completed backups can be restored.")
    path = Path(job.archive_path)
    if not path.exists():
        raise FileNotFoundError("Archive file no longer exists on disk.")
    if _sha256(path) != job.checksum:
        raise ValueError("Checksum mismatch — archive integrity cannot be trusted.")

    profile = job.profile
    safety = run_backup(
        profile, created_by=created_by, kind=BackupKind.PRE_RESTORE
    )
    if safety.status != BackupStatus.SUCCESS:
        raise RuntimeError("Pre-restore safety backup failed. Restore abandoned.")

    vendor = _db_engine()
    with tempfile.TemporaryDirectory(prefix="edflow_restore_") as tmp:
        tmp_dir = Path(tmp)
        with tarfile.open(path, "r:gz") as tar:
            tar.extractall(tmp_dir)

        database_file = tmp_dir / job.database_file
        if not database_file.exists():
            raise FileNotFoundError("Database dump missing inside archive.")

        if vendor == "sqlite3":
            db_path = Path(connection.settings_dict["NAME"])
            connection.close()
            shutil.copy2(database_file, db_path)
        elif vendor == "postgresql":
            _restore_postgres(database_file)
        else:
            raise RuntimeError(f"Unsupported database engine: {vendor}")

        media_source = tmp_dir / "media"
        if media_source.exists():
            media_root = Path(settings.MEDIA_ROOT)
            media_root.mkdir(parents=True, exist_ok=True)
            for child in media_root.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            shutil.copytree(media_source, media_root, dirs_exist_ok=True)

    job.note = (
        f"Restored on {timezone.now():%d %b %Y %H:%M} "
        f"(safety backup: {safety.archive_name})."
    )
    job.save(update_fields=["note"])
    return job


def _restore_postgres(database_file):
    db = connection.settings_dict
    env = dict(settings.DATABASES["default"])
    if db.get("PASSWORD"):
        env["PGPASSWORD"] = str(db["PASSWORD"])
    if database_file.suffix == ".dump":
        args = [
            "pg_restore", "--clean", "--if-exists", "--no-owner",
            "-d", db["NAME"],
        ]
        if db.get("HOST"):
            args += ["-h", str(db["HOST"])]
        if db.get("PORT"):
            args += ["-p", str(db["PORT"])]
        if db.get("USER"):
            args += ["-U", str(db["USER"])]
        with open(database_file, "rb") as fh:
            result = subprocess.run(
                args, input=fh.read(), env=env, capture_output=True
            )
    elif database_file.suffix == ".json":
        call_command("loaddata", str(database_file))
        return
    else:
        args = [
            "psql", "-d", db["NAME"],
        ]
        if db.get("HOST"):
            args += ["-h", str(db["HOST"])]
        if db.get("USER"):
            args += ["-U", str(db["USER"])]
        with open(database_file, "rb") as fh:
            result = subprocess.run(
                args, input=fh.read(), env=env, capture_output=True
            )
    if result.returncode != 0:
        raise RuntimeError(
            f"PostgreSQL restore failed: {result.stderr.decode(errors='replace')[:1000]}"
        )