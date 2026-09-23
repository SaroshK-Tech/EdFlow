document.addEventListener("DOMContentLoaded", function () {
    // Sidebar toggle (desktop collapse + mobile drawer)
    document.querySelectorAll("[data-sidebar-toggle]").forEach(function (el) {
        el.addEventListener("click", function () {
            var sidebar = document.getElementById("appSidebar");
            if (!sidebar) return;
            if (window.innerWidth < 992) {
                sidebar.classList.toggle("open");
                var backdrop = document.querySelector(".app-sidebar-backdrop");
                if (backdrop) backdrop.classList.toggle("show", sidebar.classList.contains("open"));
            } else {
                sidebar.classList.toggle("collapsed");
                document.body.classList.toggle("sidebar-collapsed");
                localStorage.setItem("edf_sidebar_collapsed",
                    sidebar.classList.contains("collapsed") ? "1" : "0");
            }
        });
    });

    // Restore desktop collapsed state
    var saved = localStorage.getItem("edf_sidebar_collapsed");
    if (saved === "1" && window.innerWidth >= 992) {
        var sidebar = document.getElementById("appSidebar");
        if (sidebar) sidebar.classList.add("collapsed");
    }

    // Auto-hide any rendered message toasts
    document.querySelectorAll("#msg-toasts .toast").forEach(function (t) {
        var bs = bootstrap.Toast.getOrCreateInstance(t, { delay: 4000 });
        bs.show();
    });

    // Scroll-aware topbar: shadow on scroll, hide on scroll down,
    // slide back in on scroll up.
    var topbar = document.querySelector(".app-topbar");
    if (topbar) {
        var lastY = window.scrollY;
        window.addEventListener("scroll", function () {
            var y = window.scrollY;
            topbar.classList.toggle("scrolled", y > 40);
            topbar.classList.toggle("hide", y > lastY && y > 140);
            lastY = y;
        }, { passive: true });
    }

    /* ====================================================================
       Custom scrollbars (replaces native Windows/OS scrollbars).
       Native bars are hidden by CSS (.edf-scroll-hover / -always);
       JS draws a slim thumb that syncs with real scrolling and supports
       drag, wheel and hover-triggered visibility.
       ==================================================================== */
    var CustomScrollbar = (function () {
        var instances = [];

        function thumb(track) { return track.querySelector(".edf-scrollbar-thumb"); }

        function fmt(px) { return Math.round(px) + "px"; }

        function CustomScrollbar(container, opts) {
            opts = opts || {};
            this.container = container;
            this.windowMode = opts.windowMode || false;

            var track = document.createElement("div");
            track.className = "edf-scrollbar";
            track.innerHTML = '<div class="edf-scrollbar-thumb"></div>';
            if (this.windowMode) {
                document.body.appendChild(track);
            } else {
                container.classList.add("edf-scroll-hover");
                container.style.position = container.style.position || "relative";
                track.style.position = "absolute";
                track.style.top = "0";
                track.style.right = "0";
                track.style.bottom = "auto";
                track.style.height = "100%";
                track.style.zIndex = "5";
                container.appendChild(track);
            }
            this.track = track;
            this.th = thumb(track);

            this.visible = false;
            this.hideTimer = null;

            this.onScroll = this.update.bind(this, true);
            this.resizeObserver = null;
            if (typeof ResizeObserver !== "undefined") {
                this.resizeObserver = new ResizeObserver(this.update.bind(this, false));
                this.resizeObserver.observe(container);
            }

            this.attach();
            this.update(false);
        }

        CustomScrollbar.prototype.getMetrics = function () {
            var c = this.container;
            if (this.windowMode) {
                var doc = document.documentElement;
                return {
                    client: window.innerHeight,
                    scroll: doc.scrollHeight,
                    pos: window.scrollY || doc.scrollTop || 0,
                    horizClient: window.innerWidth,
                    horizScroll: doc.scrollWidth
                };
            }
            return {
                client: c.clientHeight,
                scroll: c.scrollHeight,
                pos: c.scrollTop,
                horizClient: c.clientWidth,
                horizScroll: c.scrollWidth
            };
        };

        CustomScrollbar.prototype.update = function (showTemporarily) {
            var m = this.getMetrics();
            var overflowV = m.scroll > m.client + 1;
            var overflowH = m.horizScroll > m.horizClient + 1;

            this.track.style.display = "block";

            // Vertical thumb
            if (overflowV) {
                var thumbH = Math.max(40, (m.client / m.scroll) * m.client);
                var maxTop = m.client - thumbH;
                var scrollRange = m.scroll - m.client;
                var top = scrollRange > 0 ? (m.pos / scrollRange) * maxTop : 0;
                this.th.style.display = "block";
                this.th.style.height = fmt(thumbH);
                this.th.style.width = "";
                this.th.style.top = fmt(top);
                this.th.style.bottom = "auto";
                this.th.style.left = "auto";
                this.th.style.right = "3px";
            } else if (overflowH) {
                // Horizontal thumb
                var thumbW = Math.max(60, (m.horizClient / m.horizScroll) * m.horizClient);
                var trackW = this.horizTrack ? this.horizTrack.clientWidth : this.track.clientWidth;
                var maybeBottom = this.horizTrack ? 3 : 0;
                var hScrollRange = m.horizScroll - m.horizClient;
                var hMaxLeft = this.horizTrack
                    ? this.horizTrack.clientWidth - thumbW
                    : this.track.clientWidth - thumbW;
                var hLeft = hScrollRange > 0 ? (m.pos / hScrollRange) * hMaxLeft : 0;
                this.th.style.display = "block";
                this.th.style.width = fmt(thumbW);
                this.th.style.height = "6px";
                this.th.style.top = "auto";
                this.th.style.bottom = fmt(maybeBottom);
                this.th.style.left = fmt(hLeft);
                this.th.style.right = "auto";
            } else {
                this.track.style.display = "none";
                this.visible = false;
                return;
            }

            this.visible = true;
            if (showTemporarily) {
                this.track.classList.add("edf-scrollbar-visible");
                clearTimeout(this.hideTimer);
                var self = this;
                this.hideTimer = setTimeout(function () {
                    self.track.classList.remove("edf-scrollbar-visible");
                }, 700);
            }
        };

        CustomScrollbar.prototype.attach = function () {
            var self = this;

            this.container.addEventListener("scroll", this.onScroll, { passive: true });
            window.addEventListener("resize", function () { self.update(false); });
            this.th.addEventListener("mouseenter", function () {
                self.track.classList.add("edf-scrollbar-visible");
                clearTimeout(self.hideTimer);
            });
            this.track.addEventListener("mouseleave", function () {
                self.track.classList.remove("edf-scrollbar-visible");
            });

            // Drag to scroll (vertical or horizontal thumb)
            this.th.addEventListener("mousedown", function (e) {
                e.preventDefault();
                var isHorizontal = self.th.offsetWidth > self.th.offsetHeight;
                var start = isHorizontal ? e.clientX : e.clientY;
                var startPos = self.getMetrics().pos;
                var thumbSize = isHorizontal ? self.th.offsetWidth : self.th.offsetHeight;
                var range = self.getMetrics().scroll - self.getMetrics().client;
                self.th.classList.add("dragging");
                self.track.classList.add("edf-scrollbar-visible");

                function onMove(ev) {
                    var delta = (isHorizontal ? ev.clientX : ev.clientY) - start;
                    var ratio = (startPos + delta) / (range || 1);
                    if (self.windowMode) {
                        if (isHorizontal) window.scrollTo(ratio * range, window.scrollY);
                        else window.scrollTo(window.scrollX, ratio * range);
                    } else if (isHorizontal) {
                        self.container.scrollLeft = ratio * range;
                    } else {
                        self.container.scrollTop = ratio * range;
                    }
                }
                function onUp() {
                    document.removeEventListener("mousemove", onMove);
                    document.removeEventListener("mouseup", onUp);
                    self.th.classList.remove("dragging");
                    self.track.classList.remove("edf-scrollbar-visible");
                }
                document.addEventListener("mousemove", onMove);
                document.addEventListener("mouseup", onUp);
            });
        };

        return CustomScrollbar;
    })();

    // Window scrollbar
    document.documentElement.classList.add("edf-scroll-hover");
    new CustomScrollbar(document.documentElement, { windowMode: true });

    // Per-container scrollbars (nav + horizontally scrollable tables)
    document.querySelectorAll(".sidebar-nav, .table-responsive").forEach(function (el) {
        new CustomScrollbar(el);
    });
});