from decimal import Decimal

from django.db import transaction

from .models import (
    AppliesTo,
    ComponentKind,
    PaySlip,
    PayrollStatus,
    SalaryComponent,
)

TWO_PLACES = Decimal("0.01")


def component_value(component, basic):
    if component.amount:
        return Decimal(component.amount)
    if component.percentage:
        return (basic * Decimal(component.percentage)) / Decimal("100")
    return Decimal("0")


def applies_to_staff(component, staff):
    if component.applies_to == AppliesTo.ALL:
        return True
    if component.applies_to == AppliesTo.TEACHER:
        return staff.is_teacher
    return not staff.is_teacher


def process_run(run):
    """Compute pay slips for every active staff member (idempotent re-run).

    Re-running a run deletes and recreates its slips so results never drift.
    """
    from apps.staff.models import Staff
    from apps.students.models import Status

    components = list(SalaryComponent.objects.filter(active=True))
    staff_qs = Staff.objects.filter(status=Status.ACTIVE).select_related("department")

    with transaction.atomic():
        PaySlip.objects.filter(run=run).delete()
        slips = []
        for staff in staff_qs:
            basic = Decimal(staff.salary or 0)
            allowances = []
            deductions = []
            total_allowances = Decimal("0")
            total_deductions = Decimal("0")
            for component in components:
                if not applies_to_staff(component, staff):
                    continue
                value = component_value(component, basic).quantize(TWO_PLACES)
                row = {
                    "name": component.name,
                    "amount": str(value),
                    "is_taxable": component.is_taxable,
                    "percentage": str(component.percentage) if component.percentage else "",
                }
                if component.kind == ComponentKind.ALLOWANCE:
                    allowances.append(row)
                    total_allowances += value
                else:
                    deductions.append(row)
                    total_deductions += value
            net = (basic + total_allowances - total_deductions).quantize(TWO_PLACES)
            slips.append(
                PaySlip(
                    run=run,
                    staff=staff,
                    basic=basic.quantize(TWO_PLACES),
                    allowances_total=total_allowances.quantize(TWO_PLACES),
                    deductions_total=total_deductions.quantize(TWO_PLACES),
                    net=net,
                    data={"allowances": allowances, "deductions": deductions},
                )
            )
        PaySlip.objects.bulk_create(slips)

    run.status = PayrollStatus.PROCESSED
    run.save(update_fields=["status"])
    return len(slips)