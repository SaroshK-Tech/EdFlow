/* EdFlow live updates over WebSockets (Channels, spec §29).
   Included only for authenticated sessions; shows a toast for school-wide
   live events. Degrades silently when the socket is unavailable. */
(function () {
    "use strict";

    function toast(text, label) {
        var container = document.getElementById("msg-toasts");
        if (!container) {
            return;
        }
        var el = document.createElement("div");
        el.className = "toast align-items-center text-bg-dark border-0 show";
        el.role = "alert";
        el.innerHTML = '<div class="d-flex"><div class="toast-body"><strong>' +
            (label || "Live") + "</strong> " + String(text) +
            '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" ' +
            'data-bs-dismiss="toast" aria-label="Close"></button></div>';
        container.appendChild(el);
        if (typeof bootstrap !== "undefined" && bootstrap.Toast) {
            var t = new bootstrap.Toast(el, { delay: 6000 });
            t.show();
        }
        setTimeout(function () { el.remove(); }, 7000);
    }

    function updateTopbarNotifications(msg) {
        var dropdownMenu = document.querySelector(".topbar-icon[title='Notifications'] + .dropdown-menu");
        if (!dropdownMenu) return;

        var badgeDot = document.querySelector(".topbar-icon[title='Notifications'] .badge-dot");
        var emptyMsg = dropdownMenu.querySelector(".dropdown-item.text-muted");

        if (msg.type === "announcement.published" && msg.payload && msg.payload.url) {
            if (emptyMsg) emptyMsg.remove();

            var newItem = document.createElement("a");
            newItem.className = "dropdown-item d-flex align-items-center gap-2 small";
            newItem.href = msg.payload.url;
            newItem.style.whiteSpace = "normal";
            newItem.innerHTML = '<i class="bi bi-megaphone text-primary"></i><span>' + msg.payload.title + '</span>';
            dropdownMenu.insertBefore(newItem, dropdownMenu.querySelector(".dropdown-item"));

            if (!badgeDot) {
                var btn = document.querySelector(".topbar-icon[title='Notifications']");
                if (btn) {
                    var dot = document.createElement("span");
                    dot.className = "badge-dot";
                    btn.appendChild(dot);
                }
            }
        }
    }

    function connect() {
        try {
            var proto = window.location.protocol === "https:" ? "wss://" : "ws://";
            var ws = new WebSocket(proto + window.location.host + "/ws/school/");
            ws.onmessage = function (evt) {
                var msg;
                try { msg = JSON.parse(evt.data); } catch (e) { return; }
                if (!msg || !msg.type || msg.type === "connected") {
                    return;
                }
                var label = "Live";
                if (msg.type === "announcement.published") { label = "Announcement"; }
                if (msg.type === "attendance.updated") { label = "Attendance"; }
                if (msg.type === "queue.updated") { label = "Messages"; }
                toast(msg.type.replace(/[._]/g, " "), label);

                updateTopbarNotifications(msg);

                if (typeof window.edflowLiveEvent === "function") {
                    window.edflowLiveEvent(msg);
                }
            };
            ws.onclose = function () { setTimeout(connect, 15000); };
        } catch (e) { /* offline-first: ignore */ }
    }

    connect();
})();