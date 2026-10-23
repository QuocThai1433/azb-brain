// AZB Brain – giao diện quản trị (vanilla JS, không cần build)

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtNum = (n) => (n == null ? "—" : Number(n).toLocaleString("vi-VN"));

const UNIT_TYPES = { board: "HĐQT", executive: "Ban điều hành", division: "Khối", department: "Phòng/Ban", committee: "Ban chuyên trách", project: "Dự án" };
const COLOR_GROUPS = { exec: "Điều hành", hr: "Nhân sự - Hành chính", ops: "Vận hành", finance: "Tài chính", technical: "Kinh tế - Kỹ thuật", construction: "Thi công / Xây lắp", commercial: "Thương mại" };
const METRICS = { doanh_thu: "Doanh thu", doanh_so: "Doanh số", loi_nhuan: "Lợi nhuận", khac: "Chỉ tiêu khác" };
const PROCESS_STATUS = { draft: "Nháp", active: "Đang áp dụng", retired: "Hết hiệu lực" };
const TITLES = [["CT", "Chủ tịch HĐQT"], ["TGĐ", "Tổng Giám đốc"], ["PTGĐ", "Phó Tổng Giám đốc"], ["GĐK", "Giám đốc Khối"], ["GĐ", "Giám đốc"],
  ["TB", "Trưởng ban"], ["PB", "Phó ban"], ["TP", "Trưởng phòng"], ["PP", "Phó phòng"], ["TBP", "Trưởng bộ phận"], ["NV", "Nhân viên"]];
const color = (g) => `var(--g-${g || "exec"})`;

const DOC_STATUS = { pending: ["Chờ xử lý", "warn"], processing: ["Đang đọc...", "warn"], ok: ["Đã đánh chỉ mục", "ok"], needs_ocr: ["Chưa đọc được (cần OCR)", "bad"], failed: ["Chưa đọc được", "bad"] };
const DOC_UNREAD = new Set(["failed", "needs_ocr"]); // file chưa trích được chữ → AI chưa trả lời được từ file này
const ACCESS_LABELS = { public: "Công khai", internal: "Nội bộ", restricted: "Hạn chế", secret: "Mật" };
const DOC_LABELS = { quy_trinh: "Quy trình", quy_dinh: "Quy định", ram: "RAM phân nhiệm", huong_dan: "Hướng dẫn", bieu_mau: "Biểu mẫu", so_tay: "Sổ tay", website: "Trang web", khac: "Khác" };
// Bộ biểu tượng nét mảnh (24x24) dùng chung cho sidebar, tổng quan
const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  org: '<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/><rect x="15" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M6 16v-4h12v4"/>',
  building: '<path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/><path d="M16 9h2a2 2 0 0 1 2 2v10"/><path d="M8 7h4M8 11h4M8 15h4M2 21h20"/>',
  users: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4a4 4 0 0 1 0 8M22 21a6 6 0 0 0-4-5.6"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  chart: '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 6-6"/>',
  spark: '<path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  logout: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3"/>',
  layers: '<path d="M12 3 2 8l10 5 10-5z"/><path d="m2 13 10 5 10-5"/>',
  briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
  flow: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><path d="M10 6.5h4a3 3 0 0 1 3 3V14"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  swap: '<path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  userx: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M17 8l4 4M21 8l-4 4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
};
const icon = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const FEATURE_LABELS = { import_hr: "Nhập file HCNS", docs_view: "Xem tài liệu", docs_edit: "Sửa tài liệu (thêm/sửa/xoá)", insights: "Xem Phân tích" };
const PERM_TEMPLATES = {
  none: ["Không cấp thêm", []],
  docs: ["Xem tài liệu", ["docs_view"]],
  hr: ["Nhân viên HCNS", ["import_hr", "docs_view"]],
  lead: ["Trưởng phòng / quản lý", ["docs_view", "docs_edit", "insights"]],
};
const tplField = { name: "_tpl", label: "Mẫu quyền (chọn để tick nhanh)", type: "select", options: Object.entries(PERM_TEMPLATES).map(([k, [l]]) => [k, l]), default: "none" };
const DOC_ACTIONS = `<span class="btn-group"><button class="ghost" id="url-doc">${icon("globe")}Học từ URL</button><button class="primary" id="up-doc">${icon("upload")}Tải tài liệu lên</button></span>`;
const hydrateIcons = (root = document) => root.querySelectorAll("svg[data-icon]").forEach((s) => {
  s.setAttribute("viewBox", "0 0 24 24");
  s.setAttribute("aria-hidden", "true");
  s.innerHTML = ICONS[s.dataset.icon] || "";
  s.removeAttribute("data-icon");
  s.classList.add("ico");
});
hydrateIcons();


// Số đếm tăng dần khi trang hiện ra
function countUp(root) {
  root.querySelectorAll("[data-count]").forEach((el) => {
    const to = Number(el.dataset.count) || 0;
    const suffix = el.dataset.suffix || "";
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || to === 0) return (el.textContent = fmtNum(to) + suffix);
    const t0 = performance.now(), dur = 1100;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      el.textContent = fmtNum(Math.round(to * (1 - Math.pow(1 - p, 3)))) + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

const fmtSize = (b) => (b == null ? "" : b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.ceil(b / 1024) + " KB");

async function api(path, opts = {}) {
  const isForm = opts.body instanceof FormData;
  const res = await fetch(path, {
    headers: isForm ? {} : { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? (isForm ? opts.body : JSON.stringify(opts.body)) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    boot();
    throw new Error("Phiên đăng nhập đã hết hạn");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : res.statusText || `Lỗi máy chủ (${res.status})`);
  }
  return res.json();
}

const state = { view: "overview", unitId: null, unitTab: "org", chatId: null, chatJob: null, jobs: new Map(), jobSeq: 0, unseen: new Set(), convs: [], user: null, docQuery: "", peopleQuery: "", peopleFocus: null, openDepts: new Set(), showInactive: false };

// Thứ bậc theo ngạch lao động của HCNS – dùng để đưa người đứng đầu đơn vị lên trước
const GRADES = ["Lãnh đạo", "Giám Đốc Khối", "Trưởng Phòng Ban", "Phó Phòng Ban", "Trưởng Bộ Phận", "Phó Bộ Phận", "Trưởng nhóm", "Nhân viên"];
const GRADE_RANK = GRADES.map((g) => g.toLowerCase());
// Ngạch của Ban QLDA trong file HCNS chưa thống nhất (Chỉ huy trưởng có người xếp Phó Bộ phận) -> ưu tiên theo chức danh
const TITLE_RANK = [[/^giám đốc dự án/i, 1.5], [/^chỉ huy trưởng/i, 3.5], [/^chỉ huy phó/i, 4.5]];
const gradeRank = (e) => {
  const t = TITLE_RANK.find(([re]) => re.test(e.job_title || ""));
  if (t) return t[1];
  const i = GRADE_RANK.indexOf((e.grade || "").toLowerCase());
  return i < 0 ? GRADES.length : i;
};
const isManager = (e) => gradeRank(e) < GRADE_RANK.indexOf("nhân viên");
const sortByRank = (list) => list.sort((a, b) => gradeRank(a) - gradeRank(b) || a.sort_order - b.sort_order);
const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase();
let pollTimer = null;
// Cập nhật số yêu cầu chờ duyệt (huy hiệu ở menu của admin)
async function refreshPending() {
  if (!state.user) return;
  try {
    const st = await api("/api/auth/state");
    const prev = state.user.profile_notices || 0;
    Object.assign(state.user, { pending_requests: st.user?.pending_requests || 0, pending_links: st.user?.pending_links || 0, profile_notices: st.user?.profile_notices || 0 });
    setBadges(state.user);
    // có kết quả duyệt mới trong lúc đang dùng app: báo ngay thay vì đợi user tự mở trang
    if (state.user.profile_notices > prev && state.view !== "profile") toast("Quản trị viên vừa xử lý yêu cầu của bạn. Xem ở mục Hồ sơ của tôi.");
  } catch {}
}
function setBadges(u) {
  for (const [id, n] of [["access-badge", u.pending_requests], ["users-badge", u.pending_links], ["profile-badge", u.profile_notices]]) {
    const b = $("#" + id);
    b.textContent = n || "";
    b.hidden = !n;
  }
}
setInterval(() => { if (!document.hidden) refreshPending(); }, 30000);

// ---------------- Đăng nhập ----------------
async function boot() {
  const st = await api("/api/auth/state");
  state.user = st.user;
  state.roles = st.roles;
  document.body.classList.toggle("logged-out", !st.user);
  if (!st.user) return renderLogin(st.needs_setup);
  const u = st.user;
  const show = { chat: u.can_use_ai, myfiles: u.can_use_ai, memory: u.can_use_ai, insights: can("insights"), users: u.role === "admin", access: u.role !== "ceo", docs: can("docs_view") };
  document.querySelectorAll("#nav button").forEach((b) => (b.hidden = show[b.dataset.view] === false));
  document.querySelectorAll("#nav .nav-group").forEach((g) => {  // ẩn tiêu đề nhóm nếu không còn mục nào
    let n = g.nextElementSibling, any = false;
    while (n && !n.classList.contains("nav-group")) { if (n.tagName === "BUTTON" && !n.hidden) any = true; n = n.nextElementSibling; }
    g.hidden = !any;
  });
  setBadges(u);
  const display = u.full_name || u.username;
  const initials = display.trim().split(/\s+/).slice(-2).map((w) => w[0]).join("").toUpperCase();
  $("#userbox").innerHTML = `
    <div class="u-card"><span class="avatar">${esc(initials)}</span>
      <span class="u-meta"><b>${esc(display)}</b><small>${esc(st.roles[u.role])}</small></span></div>
    <button class="icon-btn" id="pw-btn" title="Đổi mật khẩu">${icon("key")}</button>
    <button class="icon-btn" id="logout-btn" title="Đăng xuất">${icon("logout")}</button>`;
  $("#logout-btn").onclick = async () => { await api("/api/auth/logout", { method: "POST" }); state.chatId = null; state.chatJob = null; state.jobs.clear(); state.unseen.clear(); boot(); };
  $("#pw-btn").onclick = () => openForm("Đổi mật khẩu", [
    { name: "old_password", label: "Mật khẩu hiện tại", type: "password", required: true },
    { name: "new_password", label: "Mật khẩu mới (tối thiểu 8 ký tự)", type: "password", required: true },
  ], {}, (d) => api("/api/auth/password", { method: "POST", body: d }).then(() => toast("Đã đổi mật khẩu")));
  if (show[state.view] === false) state.view = "overview";
  go(state.view);
}

function renderLogin(needsSetup) {
  clearTimeout(pollTimer);
  $("#userbox").innerHTML = "";
  $("#main").innerHTML = `
    <div class="auth">
    <section class="auth-art">
      <div class="auth-logo"><img src="/static/logo.png" alt="AZB – Build Trust on Discipline"></div>
      <div>
        <h1>Trung tâm tri thức<br><em>điều hành</em> AZB</h1>
        <p>Toàn bộ sơ đồ tổ chức, nhân sự, quy trình ISO và tài liệu công ty ở một nơi – kèm trợ lý AI hỗ trợ Ban Tổng Giám đốc ra quyết định.</p>
      </div>
      <div class="auth-feats"><span>${icon("org")} Sơ đồ tổ chức</span><span>${icon("file")} Quy trình ISO</span><span>${icon("spark")} Trợ lý AI</span></div>
    </section>
    <div class="auth-form"><div class="card login">
      <h2>${needsSetup ? "Tạo tài khoản quản trị đầu tiên" : "Đăng nhập"}</h2>
      <p class="muted" style="margin:0 0 20px">${needsSetup ? "Hệ thống chưa có tài khoản nào. Tài khoản này có toàn quyền và dùng để cấp tài khoản cho người khác." : "Chào mừng trở lại. Vui lòng đăng nhập để tiếp tục."}</p>
      <form id="login-form">
        ${needsSetup ? '<div class="field"><label>Họ tên</label><input name="full_name"></div>' : ""}
        <div class="field"><label>Tên đăng nhập</label><input name="username" required autocomplete="username"></div>
        <div class="field"><label>Mật khẩu${needsSetup ? " (tối thiểu 8 ký tự)" : ""}</label>
          <input name="password" type="password" required autocomplete="${needsSetup ? "new-password" : "current-password"}"></div>
        <div class="danger" id="login-err"></div>
        <button class="primary" style="width:100%">${needsSetup ? "Tạo tài khoản" : "Đăng nhập"} ${icon("arrow")}</button>
      </form>
    </div></div></div>`;
  $("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target.elements;
    const body = { username: f.username.value, password: f.password.value };
    if (needsSetup) body.full_name = f.full_name.value;
    try {
      await api(needsSetup ? "/api/auth/setup" : "/api/auth/login", { method: "POST", body });
      boot();
    } catch (err) {
      $("#login-err").textContent = err.message;
    }
  };
}

// ---------------- Điều hướng ----------------
document.getElementById("nav").addEventListener("click", (e) => {
  const v = e.target.closest("button")?.dataset.view;
  if (v) go(v);
});
$("#menu-btn").onclick = () => document.body.classList.toggle("nav-open");
$("#scrim").onclick = () => document.body.classList.remove("nav-open");
addEventListener("scroll", () => document.body.classList.toggle("scrolled", scrollY > 4), { passive: true });
const can = (feature) => !!state.user?.permissions?.includes(feature);
const canSee = (view) => !document.querySelector(`#nav button[data-view="${view}"]`)?.hidden;

function go(view, extra = {}) {
  const changed = view !== state.view;
  Object.assign(state, { view }, extra);
  document.body.classList.toggle("chat-mode", view === "chat");
  document.body.classList.remove("nav-open");
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  const btn = document.querySelector(`#nav button[data-view="${view}"] span`);
  if (btn) {
    $("#page-title").textContent = btn.textContent;
    document.title = `${btn.textContent} · AZB Brain`;
  }
  render(changed || !$("#main .card:not(.login)"));
}

async function render(animate = false) {
  clearTimeout(pollTimer);
  const main = $("#main");
  try {
    await VIEWS[state.view](main);
  } catch (err) {
    main.innerHTML = `<div class="card danger">Lỗi: ${esc(err.message)}</div>`;
  }
  hydrateIcons(main);
  // Chỉ chạy hiệu ứng xuất hiện khi chuyển trang, không chạy khi vẽ lại sau thao tác sửa/xoá
  if (animate) {
    main.classList.remove("enter");
    void main.offsetWidth;
    main.classList.add("enter");
    clearTimeout(main._enter);
    main._enter = setTimeout(() => main.classList.remove("enter"), 900);
    if (state.view !== "chat") scrollTo({ top: 0 });
  }
}

// ---------------- Hộp thoại xác nhận / nhập liệu (thay confirm/prompt/alert gốc) ----------------
function ask({ title, message = "", input, okText = "Đồng ý", cancelText = "Huỷ", danger = false, hideCancel = false }) {
  return new Promise((resolve) => {
    const dlg = document.createElement("dialog");
    dlg.className = "dlg";
    dlg.innerHTML = `<form method="dialog" class="dlg-form">
      <h3>${esc(title)}</h3>
      ${message ? `<p class="dlg-msg">${esc(message)}</p>` : ""}
      ${input !== undefined ? `<input class="dlg-input" type="text" value="${esc(input)}" />` : ""}
      <div class="modal-actions">
        ${hideCancel ? "" : `<button type="button" class="ghost" data-act="cancel">${esc(cancelText)}</button>`}
        <button type="submit" class="primary${danger ? " danger-fill" : ""}">${esc(okText)}</button>
      </div></form>`;
    document.body.appendChild(dlg);
    const field = dlg.querySelector(".dlg-input");
    let result = input !== undefined ? null : false;
    dlg.querySelector("form").onsubmit = () => { result = field ? field.value : true; };
    dlg.querySelector("[data-act=cancel]")?.addEventListener("click", () => dlg.close());
    dlg.addEventListener("close", () => { dlg.remove(); resolve(result); });
    dlg.showModal();
    if (field) { field.focus(); field.select(); } else dlg.querySelector(".primary").focus();
  });
}
const confirmBox = (title, message, opts = {}) => ask({ title, message, ...opts });

// Hộp thoại nhiều lựa chọn: trả về `value` của nút được bấm, hoặc null nếu đóng/huỷ
function askChoice({ title, message = "", options }) {
  return new Promise((resolve) => {
    const dlg = document.createElement("dialog");
    dlg.className = "dlg";
    dlg.innerHTML = `<form method="dialog" class="dlg-form">
      <h3>${esc(title)}</h3>${message ? `<p class="dlg-msg">${esc(message)}</p>` : ""}
      <div class="modal-actions" style="flex-wrap:wrap">${options.map((o, i) =>
        `<button type="button" data-i="${i}" class="${o.primary ? "primary" : "ghost"}${o.danger ? " danger-fill" : ""}">${esc(o.label)}</button>`).join("")}</div></form>`;
    document.body.appendChild(dlg);
    let result = null;
    dlg.querySelectorAll("[data-i]").forEach((b) => (b.onclick = () => { result = options[b.dataset.i].value; dlg.close(); }));
    dlg.addEventListener("close", () => { dlg.remove(); resolve(result); });
    dlg.showModal();
  });
}

// ---------------- Thông báo (toast) ----------------
function toast(msg, type = "ok") {
  let box = $("#toasts");
  if (!box) {
    box = document.createElement("div");
    box.id = "toasts";
    box.setAttribute("aria-live", "polite");
    box.popover = "manual";  // đưa lên top layer để không bị hộp thoại (dialog) che
    document.body.appendChild(box);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.setAttribute("role", type === "err" ? "alert" : "status");
  el.innerHTML = `<span class="toast-ico">${icon(type === "err" ? "alert" : "check")}</span><span class="toast-msg">${esc(String(msg).length > 220 ? String(msg).slice(0, 220) + "…" : msg)}</span>`;
  box.appendChild(el);
  try { box.hidePopover(); box.showPopover(); } catch {}  // mở lại để nằm trên cùng, kể cả khi đang có dialog
  const close = () => { el.classList.add("out"); setTimeout(() => el.remove(), 250); };
  el.onclick = close;
  setTimeout(close, type === "err" ? 6000 : 4000);
}

// ---------------- Modal form ----------------
function openForm(title, fields, values = {}, onSave, okLabel = "Lưu") {
  const modal = $("#modal");
  $("#modal-title").textContent = title;
  $("#modal-ok").textContent = okLabel;
  $("#modal-body").innerHTML = fields
    .map((f) => {
      const v = values[f.name] == null || values[f.name] === "" ? f.default ?? "" : values[f.name];
      let input;
      if (f.type === "select" && f.search) {  // ô tìm kiếm + danh sách kết quả (thay cho select dài)
        const cur = f.options.find(([val], i) => i > 0 && String(val) === String(v));
        input = `<div class="combo" data-combo="${f.name}"><input type="hidden" name="${f.name}" value="${esc(cur ? cur[0] : "")}">
          <input type="search" class="combo-q" placeholder="${esc(f.placeholder || "Gõ tên để tìm...")}" autocomplete="off" value="${esc(cur ? cur[1] : "")}">
          <div class="combo-list" hidden></div></div>`;
      } else if (f.type === "select") {
        input = `<select name="${f.name}">${f.options
          .map(([val, lbl]) => `<option value="${esc(val)}" ${String(val) === String(v) ? "selected" : ""}>${esc(lbl)}</option>`)
          .join("")}</select>`;
      } else if (f.type === "textarea") {
        input = `<textarea name="${f.name}" placeholder="${esc(f.placeholder || "")}" ${f.required ? "required" : ""}>${esc(v)}</textarea>`;
      } else if (f.type === "info") {
        return `<p class="muted" style="margin:0 0 8px">${esc(f.label)}</p>`;
      } else if (f.type === "check") {
        return `<label class="check"><input type="checkbox" name="${f.name}" ${v ? "checked" : ""}><span>${esc(f.label)}</span></label>`;
      } else if (f.type === "file") {
        input = `<input name="${f.name}" type="file" accept="${esc(f.accept || "")}" ${f.required ? "required" : ""}>`;
      } else {
        input = `<input name="${f.name}" type="${f.type || "text"}" value="${esc(v)}" placeholder="${esc(f.placeholder || "")}" ${f.required ? "required" : ""} step="any"${f.type === "password" ? ' autocomplete="new-password" readonly onfocus="this.readOnly=false"' : ""}>`;
      }
      return `<div class="field"><label>${esc(f.label)}</label>${input}</div>`;
    })
    .join("");
  const form = $("#modal-form");
  // Ô lọc cho select dài (field.search): gõ không dấu cũng khớp; giữ lại mục đang chọn và dòng đầu ("— Chọn —")
  const plain = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
  fields.filter((f) => f.type === "select" && f.search).forEach((f) => {
    const root = form.querySelector(`[data-combo="${f.name}"]`), hidden = form.elements[f.name];
    const box = root.querySelector(".combo-q"), list = root.querySelector(".combo-list");
    const items = f.options.slice(1);  // bỏ dòng đầu ("— Chọn —"): để trống ô tìm kiếm nghĩa là không chọn ai
    const show = () => {
      const q = plain(box.value.trim());
      const hits = items.filter(([, lbl]) => !q || plain(lbl).includes(q));
      list.innerHTML = hits.length
        ? hits.map(([val, lbl]) => `<button type="button" class="combo-item ${String(val) === hidden.value ? "on" : ""}" data-val="${esc(val)}">${esc(lbl)}</button>`).join("")
        : '<div class="combo-empty">Không tìm thấy ai khớp.</div>';
      list.hidden = false;
      move(0, true);
    };
    // ↑/↓ di chuyển dòng đang tô sáng (mặc định dòng đầu), Enter chọn dòng đó
    let at = 0;
    const move = (step, reset) => {
      const els = [...list.querySelectorAll(".combo-item")];
      if (!els.length) return;
      at = reset ? 0 : (at + step + els.length) % els.length;
      els.forEach((el, i) => el.classList.toggle("hl", i === at));
      els[at].scrollIntoView({ block: "nearest" });
    };
    box.oninput = () => { hidden.value = ""; show(); };  // sửa chữ thì bỏ lựa chọn cũ, phải bấm chọn lại
    box.onfocus = () => { if (!hidden.value) show(); };
    box.onkeydown = (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (list.hidden) show();
        else move(e.key === "ArrowDown" ? 1 : -1);
      } else if (e.key === "Enter" && !list.hidden) {
        e.preventDefault();
        list.querySelector(".combo-item.hl")?.click();
      } else if (e.key === "Escape" && !list.hidden) {
        e.stopPropagation(); e.preventDefault();  // đóng danh sách, không đóng cả hộp thoại
        list.hidden = true;
      }
    };
    list.onmousedown = (e) => e.preventDefault();  // giữ focus ở ô tìm kiếm khi bấm vào kết quả
    list.onclick = (e) => {
      const b = e.target.closest(".combo-item");
      if (!b) return;
      hidden.value = b.dataset.val;
      box.value = b.textContent;
      list.hidden = true;
    };
    box.onblur = () => { list.hidden = true; };
  });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const data = {};
    fields.forEach((f) => {
      if (f.type === "file") return (data[f.name] = form.elements[f.name].files[0]);
      if (f.type === "info") return;
      if (f.type === "check") return (data[f.name] = form.elements[f.name].checked);
      let val = form.elements[f.name].value;
      if (f.type === "number" || f.numeric) val = val === "" ? null : Number(val);
      data[f.name] = val;
    });
    const ok = $("#modal-ok");
    ok.disabled = true;
    try {
      await onSave(data);
      modal.close();
      render();
    } catch (err) {
      toast("Không lưu được: " + err.message, "err");
    } finally {
      ok.disabled = false;
    }
  };
  $("#modal-cancel").onclick = () => modal.close();
  modal.showModal();
}

async function confirmDelete(table, id, label, after) {
  if (!(await ask({ title: `Xoá ${label}?`, message: "Thao tác này không thể hoàn tác.", okText: "Xoá", danger: true }))) return;
  await api(`/api/${table}/${id}`, { method: "DELETE" });
  after?.();
  render();
}

// ---------------- Views ----------------
const VIEWS = {
  async overview(main) {
    if (!main.querySelector(".hero")) main.innerHTML = `<div class="skel-wrap"><div class="skel" style="height:230px"></div>
      <div class="kpis" style="margin:0">${'<div class="skel" style="height:150px"></div>'.repeat(4)}</div>
      <div class="ov-grid" style="margin:0"><div class="skel" style="height:320px"></div><div class="skel" style="height:320px"></div></div></div>`;
    if (!can("insights")) {  // tài khoản không có quyền Phân tích: tổng quan dùng dữ liệu được phép xem
      const [emps, units, docs] = await Promise.all([
        api("/api/employees"), api("/api/units"), can("docs_view") ? api("/api/documents").catch(() => []) : Promise.resolve([]),
      ]);
      const pct = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);
      const active = emps.filter((e) => e.status !== "inactive");
      const countType = (t) => units.filter((u) => u.unit_type === t).length;
      const divisions = countType("division"), departments = countType("department");
      const byDiv = {};
      active.forEach((e) => (byDiv[e.hr_division || "Chưa phân khối"] = (byDiv[e.hr_division || "Chưa phân khối"] || 0) + 1));
      const divs = Object.entries(byDiv).sort((a, b) => b[1] - a[1]);
      const maxDiv = Math.max(1, ...divs.map(([, n]) => n));
      const hour = new Date().getHours();
      const hello = hour < 11 ? "Chào buổi sáng" : hour < 14 ? "Chào buổi trưa" : hour < 18 ? "Chào buổi chiều" : "Chào buổi tối";
      const today = new Date().toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
      const name = state.user.full_name || state.user.username;
      const nav = (v) => (canSee(v) ? `onclick="go('${v}')"` : "");
      const kpi = (ico, label, n, sub, bar, view) => `
        <div class="card kpi" ${nav(view)}>
          <div class="kpi-top"><span class="kpi-ico">${icon(ico)}</span>${canSee(view) ? `<span class="kpi-go">${icon("arrow")}</span>` : ""}</div>
          <div class="kpi-num" data-count="${n}">0</div><div class="kpi-lbl">${label}</div>
          <div class="kpi-sub">${sub}</div><div class="kpi-bar"><i data-w="${bar}"></i></div></div>`;
      const quick = [["org", "Sơ đồ tổ chức", "Cơ cấu điều hành", "chart"], ["building", "Phòng ban", "Chức năng, quy trình", "units"],
        ["users", "Nhân sự", "Danh sách HCNS", "people"], ["file", "Kho tài liệu", "ISO, biểu mẫu", "docs"]].filter(([, , , v]) => canSee(v));
      main.innerHTML = `
        <section class="hero">
          <div>
            <span class="hero-date"><i></i>${esc(today.charAt(0).toUpperCase() + today.slice(1))}</span>
            <h1>${hello}, <em>${esc(name)}</em></h1>
            <p>Tổng quan Công ty Cổ phần AZB: cơ cấu tổ chức, phòng ban và nhân sự theo sơ đồ điều hành hiện hành.</p>
            <div class="hero-actions"><button class="ghost" onclick="go('chart')">${icon("org")} Xem sơ đồ tổ chức</button></div>
          </div>
          <div class="hero-panel">
            <div class="hp-head"><span>Quy mô công ty</span></div>
            <div class="hero-kpis">
              <div><b data-count="${units.length}">0</b><span>Đơn vị trong sơ đồ</span></div>
              <div><b data-count="${active.length}">0</b><span>Nhân sự đang làm việc</span></div>
              ${can("docs_view") ? `<div><b data-count="${docs.length}">0</b><span>Tài liệu đã lưu</span></div>` : ""}
            </div>
          </div>
        </section>
        <div class="kpis">
          ${kpi("users", "Nhân sự đang làm việc", active.length, `${fmtNum(emps.length - active.length)} người đã nghỉ trong hồ sơ`, pct(active.length, emps.length), "people")}
          ${kpi("layers", "Khối điều hành", divisions, `${fmtNum(departments)} phòng / ban trực thuộc`, 100, "chart")}
          ${kpi("building", "Đơn vị trong sơ đồ", units.length, "Gồm khối, phòng ban và công trình", 100, "units")}
        </div>
        <div class="ov-grid">
          <div class="card">
            <div class="card-head"><h3><span class="ico-chip">${icon("users")}</span><span>Nhân sự theo khối<span class="sub">Người đang làm việc, theo danh sách HCNS</span></span></h3>
              ${canSee("people") ? `<button class="link" onclick="go('people')">Xem tất cả →</button>` : ""}</div>
            ${divs.length ? `<div class="hbars">${divs.map(([d, n]) => `
              <div class="hbar"><span class="nm" title="${esc(d)}">${esc(d)}</span>
                <span class="track"><span class="fill" data-w="${(n / maxDiv) * 100}"></span></span><b class="v">${fmtNum(n)}</b>
                <span class="tip" style="--x:${34 + (n / maxDiv) * 33}%">${esc(d)}: <b>${fmtNum(n)}</b> người · ${pct(n, active.length)}%</span></div>`).join("")}</div>
              <div class="chart-foot"><span>${divs.length} khối / nhóm</span><span>Tổng <b>${fmtNum(active.length)}</b> người</span></div>`
              : '<div class="empty">Chưa có danh sách nhân sự.</div>'}
          </div>
          <div class="card">
            <div class="card-head"><h3><span class="ico-chip">${icon("spark")}</span>Truy cập nhanh</h3></div>
            <div class="quick">${quick.map(([ic, t, d, v]) => `<button onclick="go('${v}')">${icon(ic)}<b>${t}</b><span>${d}</span></button>`).join("")}</div>
          </div>
        </div>`;
      countUp(main);
      requestAnimationFrame(() => requestAnimationFrame(() => main.querySelectorAll("[data-w]").forEach((el) => (el.style.width = el.dataset.w + "%"))));
      return;
    }
    const [ins, ai, emps, units, docs] = await Promise.all([
      api("/api/insights"), api("/api/ai/status"), api("/api/employees"), api("/api/units"), can("docs_view") ? api("/api/documents").catch(() => []) : Promise.resolve([]),
    ]);
    const s = ins.stats;
    const pct = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);
    const active = emps.filter((e) => e.status !== "inactive");

    // Nhân sự đang làm việc theo khối (theo danh sách HCNS)
    const byDiv = {};
    active.forEach((e) => (byDiv[e.hr_division || "Chưa phân khối"] = (byDiv[e.hr_division || "Chưa phân khối"] || 0) + 1));
    const divs = Object.entries(byDiv).sort((a, b) => b[1] - a[1]);
    const maxDiv = Math.max(1, ...divs.map(([, n]) => n));

    // Mức độ hoàn thiện dữ liệu – mỗi chỉ số là tỷ lệ phần đã có trên tổng
    const countType = (types) => units.filter((u) => types.includes(u.unit_type)).length;
    const meters = [
      ["Chức danh đã có người đảm nhiệm", s.positions - s.vacancies, s.positions],
      ["Phòng/ban đã có quy trình", s.departments - ins.units_without_process.length, s.departments],
      ["Khối/phòng đã có mục tiêu", countType(["division", "department"]) - ins.units_without_target.length, countType(["division", "department"])],
      ["Đơn vị đã xác nhận tên", units.length - ins.unverified.units.length, units.length],
      ["Nhân sự đủ họ tên", emps.length - ins.unverified.employees.length, emps.length],
    ].filter(([, , whole]) => whole > 0);
    const health = meters.length ? Math.round(meters.reduce((t, [, p, w]) => t + pct(p, w), 0) / meters.length) : 0;

    const hour = new Date().getHours();
    const hello = hour < 11 ? "Chào buổi sáng" : hour < 14 ? "Chào buổi trưa" : hour < 18 ? "Chào buổi chiều" : "Chào buổi tối";
    const today = new Date().toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });
    const name = state.user.full_name || state.user.username;
    const nav = (v, extra = "") => (canSee(v) ? `onclick="go('${v}'${extra})"` : "");

    const kpi = (ico, label, n, sub, bar, view, warn) => `
      <div class="card kpi ${warn ? "warn" : ""}" ${nav(view)}>
        <div class="kpi-top"><span class="kpi-ico">${icon(ico)}</span>${canSee(view) ? `<span class="kpi-go">${icon("arrow")}</span>` : ""}</div>
        <div class="kpi-num" data-count="${n}">0</div>
        <div class="kpi-lbl">${label}</div>
        <div class="kpi-sub">${sub}</div>
        <div class="kpi-bar"><i data-w="${bar}"></i></div>
      </div>`;
    const alert = (ico, title, desc, n, view, cls = "") => `
      <div class="alert-item" ${nav(view)}>
        <span class="dotc ${cls}">${icon(ico)}</span>
        <span class="tx"><b>${title}</b><span>${desc}</span></span>
        <span class="n">${n}</span>
      </div>`;
    const vacTitles = [...new Set(ins.vacancies.map((v) => v.unit_name))].slice(0, 3).join(", ");

    main.innerHTML = `
      <section class="hero">
        <svg class="hero-skyline" viewBox="0 0 600 300" preserveAspectRatio="xMaxYMax meet" fill="#fff" aria-hidden="true">
          <rect x="40" y="170" width="60" height="130"/><rect x="110" y="120" width="70" height="180"/><rect x="190" y="200" width="40" height="100"/>
          <rect x="240" y="80" width="80" height="220"/><rect x="330" y="150" width="55" height="150"/><rect x="395" y="110" width="65" height="190"/>
          <rect x="470" y="190" width="50" height="110"/><rect x="530" y="140" width="70" height="160"/>
          <path d="M280 80V20h4v60zM200 30h170v6H200zM360 36v40h3V36z" /><rect x="352" y="76" width="18" height="12"/>
        </svg>
        <div>
          <span class="hero-date"><i></i>${esc(today.charAt(0).toUpperCase() + today.slice(1))}</span>
          <h1>${hello}, <em>${esc(name)}</em></h1>
          <p>Bức tranh toàn cảnh Công ty Cổ phần AZB: cơ cấu tổ chức, nhân sự, quy trình và mức độ sẵn sàng của dữ liệu cho trợ lý AI.</p>
          <div class="hero-actions">
            ${canSee("chat") ? `<button class="primary accent" onclick="go('chat')">${icon("spark")} Hỏi trợ lý AI</button>` : ""}
            <button class="ghost" onclick="go('chart')">${icon("org")} Xem sơ đồ tổ chức</button>
          </div>
        </div>
        <div class="hero-panel">
          <div class="hp-head"><span>Kho tri thức công ty</span>
            <span class="ai-pill ${ai.configured ? "on" : "off"}">${ai.configured ? "● AI sẵn sàng" : "● AI chưa cấu hình"}</span></div>
          <div class="hero-kpis">
            <div><b data-count="${units.length}">0</b><span>Đơn vị trong sơ đồ</span></div>
            ${can("docs_view") ? `<div><b data-count="${docs.length}">0</b><span>Tài liệu đã lưu</span></div>` : ""}
            <div><b data-count="${s.processes}">0</b><span>Quy trình</span></div>
            <div><b data-count="${s.targets}">0</b><span>Mục tiêu kinh doanh</span></div>
          </div>
        </div>
      </section>

      <div class="kpis">
        ${kpi("users", "Nhân sự đang làm việc", s.employees, `${fmtNum(emps.length - active.length)} người đã nghỉ trong hồ sơ`, pct(s.employees, emps.length), "people")}
        ${kpi("layers", "Khối điều hành", s.divisions, `${fmtNum(s.departments)} phòng / ban trực thuộc`, 100, "chart")}
        ${kpi("briefcase", "Chức danh trên sơ đồ", s.positions, `${pct(s.positions - s.vacancies, s.positions)}% đã có người đảm nhiệm`, pct(s.positions - s.vacancies, s.positions), "units")}
        ${kpi("userx", "Vị trí đang trống", s.vacancies, s.vacancies ? "Cần tuyển dụng hoặc bổ nhiệm" : "Đã đủ người", pct(s.vacancies, s.positions), "insights", s.vacancies > 0)}
      </div>

      <div class="ov-grid">
        <div class="card">
          <div class="card-head"><h3><span class="ico-chip">${icon("users")}</span><span>Nhân sự theo khối<span class="sub">Người đang làm việc, theo danh sách HCNS</span></span></h3>
            ${canSee("people") ? `<button class="link" onclick="go('people')">Xem tất cả →</button>` : ""}</div>
          ${divs.length ? `<div class="hbars">${divs.map(([d, n]) => `
            <div class="hbar"><span class="nm" title="${esc(d)}">${esc(d)}</span>
              <span class="track"><span class="fill" data-w="${(n / maxDiv) * 100}"></span></span><b class="v">${fmtNum(n)}</b>
              <span class="tip" style="--x:${34 + (n / maxDiv) * 33}%">${esc(d)}: <b>${fmtNum(n)}</b> người · ${pct(n, active.length)}%</span></div>`).join("")}</div>
            <div class="chart-foot"><span>${divs.length} khối / nhóm</span><span>Tổng <b>${fmtNum(active.length)}</b> người</span></div>`
            : '<div class="empty">Chưa có danh sách nhân sự. Nhập file HCNS ở trang Nhân sự.</div>'}
        </div>
        <div class="card">
          <div class="card-head"><h3><span class="ico-chip">${icon("check")}</span><span>Mức độ hoàn thiện dữ liệu<span class="sub">Càng đầy đủ, AI tư vấn càng chính xác</span></span></h3></div>
          <div class="health">
            <div class="ring">
              <svg viewBox="0 0 120 120"><defs><linearGradient id="ring-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#2a73c2"/><stop offset="1" stop-color="#004c97"/></linearGradient></defs>
                <circle class="bg" cx="60" cy="60" r="54"/><circle class="fg" cx="60" cy="60" r="54" data-pct="${health}"/></svg>
              <div class="c"><b data-count="${health}" data-suffix="%">0</b><span>Tổng thể</span></div>
            </div>
            <div class="meters">${meters.map(([l, p, w]) => `
              <div class="meter ${pct(p, w) < 50 ? "low" : ""}" title="${fmtNum(p)}/${fmtNum(w)}">
                <div class="row"><span>${l}</span><b>${pct(p, w)}%</b></div><div class="bar"><i data-w="${pct(p, w)}"></i></div></div>`).join("")}
            </div>
          </div>
          <p class="health-note">${icon("info")}<span>Trợ lý AI tra cứu trực tiếp cơ sở dữ liệu mỗi lần trả lời – dữ liệu mới nhập được dùng ngay.</span></p>
        </div>
      </div>

      <div class="ov-grid three">
        <div class="card">
          <div class="card-head"><h3><span class="ico-chip">${icon("alert")}</span>Cần chú ý</h3></div>
          <div class="alerts">
            ${alert("userx", "Vị trí đang trống", vacTitles || "Không có vị trí trống", s.vacancies, "insights")}
            ${alert("swap", "Người kiêm nhiệm", "Giữ chức danh ở nhiều đơn vị", ins.concurrent_roles.length, "insights")}
            ${alert("briefcase", "Phòng do cấp phó phụ trách", "Chưa có Trưởng phòng", ins.deputy_led_departments.length, "insights")}
            ${alert("info", "Dữ liệu cần xác nhận", "Tên đơn vị / họ tên nhân sự", ins.unverified.units.length + ins.unverified.employees.length, "insights", "b")}
          </div>
        </div>
        <div class="card">
          <div class="card-head"><h3><span class="ico-chip">${icon("spark")}</span>Truy cập nhanh</h3></div>
          <div class="quick">
            ${[["org", "Sơ đồ tổ chức", "Cơ cấu điều hành", "chart"], ["building", "Phòng ban", "Chức năng, quy trình", "units"],
               ["file", "Kho tài liệu", "ISO, biểu mẫu", "docs"], ["chart", "Phân tích", "Chỉ dấu tổ chức", "insights"],
               ["users", "Nhân sự", "Danh sách HCNS", "people"], ["spark", "Trợ lý AI", ai.configured ? "Sẵn sàng" : "Chưa cấu hình", "chat"]]
              .filter(([, , , v]) => canSee(v)).slice(0, 4)
              .map(([ic, t, d, v]) => `<button onclick="go('${v}')">${icon(ic)}<b>${t}</b><span>${d}</span></button>`).join("")}
          </div>
        </div>
        <div class="card source">
          <div class="card-head"><h3><span class="ico-chip">${icon("flow")}</span>Nguồn dữ liệu</h3></div>
          <div class="timeline">
            <div><b>Sơ đồ điều hành AZB-SDTC-REV02</b><small>Ngày 01/08/2026 · TGĐ Trần Minh Nhơn ký</small></div>
            <div><b>Danh sách nhân sự HCNS</b><small>${fmtNum(emps.length)} hồ sơ · cập nhật hằng tuần theo mã NV</small></div>
            <div class="acc"><b>Trợ lý AI</b><small>${ai.configured ? `${esc(ai.provider || "")} · ${esc(ai.model)}` : "Chưa cấu hình API key"}</small></div>
          </div>
        </div>
      </div>`;

    countUp(main);
    // Kích hoạt các thanh / vòng tròn ở khung hình kế tiếp để có chuyển động
    requestAnimationFrame(() => requestAnimationFrame(() => {
      main.querySelectorAll("[data-w]").forEach((el) => (el.style.width = el.dataset.w + "%"));
      const ring = main.querySelector(".ring .fg");
      if (ring) ring.style.strokeDashoffset = 339.3 * (1 - ring.dataset.pct / 100);
    }));
  },

  async chart(main) {
    const tree = await api("/api/tree");
    const hdqt = tree[0];
    const ksnb = hdqt.children.find((c) => c.code === "KSNB");
    const tgd = hdqt.children.find((c) => c.code === "TGD");
    const troly = tgd.children.find((c) => c.code === "TROLY");
    const bqlda = tgd.children.find((c) => c.code === "BQLDA");
    const cols = tgd.children.filter((c) => c !== troly && c !== bqlda);

    const headTxt = (u) => (u.head ? `${esc(u.head.title_code)}. ${esc(u.head.name)}` : "");
    const bar = (u, bg) =>
      `<div class="org-bar" style="background:${bg}" onclick="go('units',{unitId:${u.id}})">
         <div class="t">${esc(u.name)}</div><div>${headTxt(u)}</div></div>`;
    const node = (u) => `
      <div class="org-node ${u.head && u.head.name === "TBA" ? "tba" : ""}" style="--c:${color(u.color_group)}"
           onclick="event.stopPropagation(); go('units',{unitId:${u.id}})">
        <div class="n">${esc(u.name)} ${u.verified ? "" : '<span class="badge warn" title="Cần xác nhận">?</span>'}</div>
        <div class="h">${headTxt(u) || "—"}</div>
      </div>
      ${u.children.length ? `<div class="org-children">${u.children.map(node).join("")}</div>` : ""}`;

    main.innerHTML = `
      <div class="page-head"><div><h2>Sơ đồ điều hành</h2><p>AZB-SDTC-REV02 · hiệu lực 01/08/2026</p></div></div>
      <div class="legend">${Object.entries(COLOR_GROUPS).map(([k, v]) => `<span><i style="background:${color(k)}"></i>${v}</span>`).join("")}
        <span><span class="badge warn">?</span> cần xác nhận</span></div>
      <div class="org-row">${bar(hdqt, color("exec"))}</div>
      <div class="org-row">${bar(ksnb, color("exec"))}</div>
      <div class="org-row">${bar(tgd, color("hr"))}</div>
      <div class="org-row org-sub">${bar(troly, color("hr"))}</div>
      <div class="org-cols">${cols.map((c) => `<div class="org-col">${node(c)}</div>`).join("")}</div>
      <div class="org-row" style="margin-top:12px">${bar(bqlda, color("exec"))}</div>
      <p class="muted">Bấm vào ô bất kỳ để xem chi tiết đơn vị. Tất cả phòng ban hỗ trợ các Ban Quản lý Dự án.</p>`;
  },

  async units(main) {
    const units = await api("/api/units");
    if (!state.unitId) state.unitId = units.find((u) => u.unit_type === "division")?.id || units[0].id;
    const u = await api(`/api/units/${state.unitId}`);

    // Duyệt cây theo chiều sâu để đơn vị con nằm ngay dưới đơn vị cha
    const depth = {};
    const ordered = [];
    const walk = (parentId, d) =>
      units.filter((x) => (x.parent_id ?? null) === parentId).forEach((x) => {
        depth[x.id] = d;
        ordered.push(x);
        walk(x.id, d + 1);
      });
    walk(null, 0);
    const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase();
    const buildTree = (query) => {
      const q = norm(query.trim());
      let visible = ordered;
      if (q) {
        // Giữ lại đơn vị khớp và các đơn vị cấp trên để còn thấy ngữ cảnh
        const keep = new Set();
        const byId = Object.fromEntries(units.map((x) => [x.id, x]));
        ordered.forEach((x) => {
          if (norm(`${x.name} ${x.full_name || ""} ${x.code || ""}`).includes(q)) {
            for (let p = x; p && !keep.has(p.id); p = byId[p.parent_id]) keep.add(p.id);
          }
        });
        visible = ordered.filter((x) => keep.has(x.id));
        if (!visible.length) return '<div class="muted" style="padding:8px">Không tìm thấy phòng ban.</div>';
      }
      return visible
        .map((x) => `
        <div class="tree-item ${x.id === u.id ? "active" : ""}" style="padding-left:${8 + depth[x.id] * 14}px; --c:${color(x.color_group)}"
             onclick="go('units',{unitId:${x.id}})">
          <span class="dot"></span><span class="lbl">${esc(x.name)}</span>
          ${x.process_count ? `<span class="badge" title="Quy trình">${x.process_count}</span>` : ""}
        </div>`)
        .join("");
    };
    state.unitQuery = state.unitQuery || "";
    const treeHtml = buildTree(state.unitQuery);

    const oldTree = main.querySelector(".tree");
    const treeScroll = oldTree ? oldTree.scrollTop : 0;
    const pageScroll = window.scrollY;
    main.style.minHeight = main.offsetHeight + "px"; // tránh trang bị co lại làm mất vị trí cuộn
    main.innerHTML = `
      <div class="split">
        <div class="card tree">
          <div class="toolbar"><b>Đơn vị</b><button class="link" id="add-unit">+ Thêm</button></div>
          <input type="search" id="unit-search" class="tree-search" placeholder="Tìm phòng ban…" value="${esc(state.unitQuery)}" autocomplete="off">
          <div id="tree-list">${treeHtml}</div>
        </div>
        <div class="card ${u.can_edit ? "" : "readonly"}">
          <div class="toolbar">
            <div>
              <h2 style="margin:0">${esc(u.name)} ${u.verified ? "" : '<span class="badge warn">Cần xác nhận</span>'}</h2>
              <div class="muted">${esc(u.full_name || "")} · ${UNIT_TYPES[u.unit_type] || u.unit_type}
                ${u.parent ? ` · trực thuộc <button class="link" onclick="go('units',{unitId:${u.parent.id}})">${esc(u.parent.name)}</button>` : ""}</div>
            </div>
            <div><button class="ghost" id="edit-unit">Sửa</button> <button class="ghost danger" id="del-unit">Xoá</button></div>
          </div>
          <div class="tabs">
            ${[["org", "Sơ đồ & nhân sự"], ["process", `Quy trình (${u.processes.length})`], ...(can("docs_view") ? [["docs", `Tài liệu (${u.documents.length})`]] : []), ["target", `Mục tiêu (${u.targets.length})`], ["info", "Chức năng"]]
              .map(([k, l]) => `<button data-tab="${k}" class="${state.unitTab === k ? "active" : ""}">${l}</button>`).join("")}
          </div>
          <div id="tab-body"></div>
        </div>
      </div>`;

    main.querySelector(".tree").scrollTop = treeScroll;
    $("#unit-search").oninput = (e) => {
      state.unitQuery = e.target.value;
      $("#tree-list").innerHTML = buildTree(state.unitQuery);
    };

    main.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => go("units", { unitTab: b.dataset.tab })));
    $("#add-unit").onclick = () => unitForm(units, { parent_id: u.id });
    $("#edit-unit").onclick = () => unitForm(units, u);
    $("#del-unit").onclick = () => confirmDelete("units", u.id, `đơn vị "${u.name}" (kèm chức danh, quy trình, mục tiêu)`, () => (state.unitId = null));

    const body = $("#tab-body");
    if (state.unitTab === "docs" && !can("docs_view")) state.unitTab = "org";
    await UNIT_TABS[state.unitTab](body, u);

    // Giữ nguyên vị trí cuộn của trang sau khi nội dung đã vẽ xong
    main.style.minHeight = "";
    window.scrollTo(0, pageScroll);
  },

  async people(main) {
    const emps = (await api("/api/employees")).filter((e) => state.showInactive || e.status !== "inactive");
    const canImport = can("import_hr");
    const canEditEmp = !!state.user.edit_all;  // chỉ admin / Ban TGĐ được thêm, sửa nhân sự
    // Nhóm theo phòng ban (theo danh sách HCNS), giữ thứ tự trong file; trong nhóm đưa người đứng đầu lên trước
    const groups = new Map();
    emps.forEach((e) => {
      const key = e.hr_department || "Chưa có trong danh sách HCNS";
      if (!groups.has(key)) groups.set(key, { name: key, division: e.hr_division || "Khác", unit_id: e.unit_id, people: [] });
      groups.get(key).people.push(e);
    });
    const list = [...groups.values()].sort((a, b) => !a.people[0].hr_department - !b.people[0].hr_department);
    list.forEach((g) => sortByRank(g.people));

    // Tìm theo từng từ (không dấu): "tran hoang" vẫn ra "Trần Quốc Hoàng"
    const words = (q) => q.split(/\s+/).filter(Boolean);
    const hay = (e) => norm([e.employee_code, e.full_name, e.job_title, e.grade].join(" "));
    const matchAll = (e, ws) => ws.every((w) => hay(e).includes(w));
    const row = (e, isHead) => `
      <tr data-emp="${e.id}" class="${e.status === "inactive" ? "muted" : ""} ${e.id === state.peopleFocus ? "focus" : ""}">
        <td>${e.employee_code ? `<span class="badge">${esc(e.employee_code)}</span>` : ""}</td>
        <td><b>${esc(e.full_name)}</b> ${isHead ? '<span class="badge ok">Phụ trách</span>' : ""}
          ${e.verified ? "" : '<span class="badge warn">Cần bổ sung tên</span>'} ${e.status === "inactive" ? '<span class="badge warn">Đã nghỉ</span>' : ""}</td>
        <td>${esc(e.job_title || e.grade || "Nhân viên")}${e.roles.length ? `<div class="muted small">Sơ đồ: ${e.roles.map((r) => esc(r.title + " – " + r.unit_name)).join("; ")}</div>` : ""}</td>
        <td class="muted">${esc(e.grade || "")}</td>
        <td>${canEditEmp ? `<button class="link" data-edit="${e.id}">Sửa</button>` : ""}</td>
      </tr>`;

    const divTotal = {};
    list.forEach((g) => (divTotal[g.division] = (divTotal[g.division] || 0) + g.people.length));
    const listHtml = (q) => {
      const ws = words(q);
      let html = "", division = null, shown = 0;
      list.forEach((g) => {
        const people = g.people.filter((e) => matchAll(e, ws));
        if (!people.length) return;
        shown += people.length;
        if (g.division !== division) {
          division = g.division;
          html += `<h3 class="div-title">${esc(division)} <span class="muted">· ${divTotal[division]} người</span></h3>`;
        }
        const head = isManager(g.people[0]) ? g.people[0] : null; // nhóm toàn nhân viên thì không có người phụ trách
        html += `
          <details class="dept card" data-dept="${esc(g.name)}" ${q || state.openDepts.has(g.name) ? "open" : ""}>
            <summary>
              <span class="dept-name">${esc(g.name)}</span>
              <span class="dept-head muted">${head ? `${esc(head.full_name)} · ${esc(head.job_title || head.grade || "")}` : "Chưa có cấp quản lý"}</span>
              <span class="badge">${q ? `${people.length}/` : ""}${g.people.length} người</span>
              ${g.unit_id ? `<button class="link" onclick="event.preventDefault(); go('units',{unitId:${g.unit_id}, unitTab:'org'})">Đơn vị →</button>` : ""}
            </summary>
            <table>
              <tr><th style="width:90px">Mã NV</th><th>Họ tên</th><th>Chức danh</th><th>Ngạch</th><th></th></tr>
              ${people.map((e) => row(e, e === head)).join("")}
            </table>
          </details>`;
      });
      return (html || '<div class="empty">Không tìm thấy nhân sự phù hợp.</div>') + (q ? `<p class="muted">Tìm thấy ${shown} người.</p>` : "");
    };

    main.innerHTML = `
      <div class="toolbar"><h2 style="margin:0">Nhân sự (${emps.length})</h2>
        <div>${canImport ? '<button class="ghost" id="import-emp">Nhập file HCNS</button> ' : ""}${canEditEmp ? '<button class="primary" id="add-emp">+ Thêm nhân sự</button>' : ""}</div></div>
      <div class="toolbar people-tools">
        <div class="people-search">
          <input id="people-q" placeholder="Tìm theo tên, mã NV, chức danh (không cần gõ dấu)..." value="${esc(state.peopleQuery)}"
            autocomplete="off" role="combobox" aria-autocomplete="list" aria-controls="people-suggest" aria-expanded="false">
          <div id="people-suggest" class="emp-suggest" role="listbox" hidden></div>
        </div>
        <button class="ghost" id="expand-all">Mở tất cả</button><button class="ghost" id="collapse-all">Thu gọn</button>
        <label class="muted"><input type="checkbox" id="show-inactive" ${state.showInactive ? "checked" : ""}> Hiện người đã nghỉ</label>
      </div>
      <div id="people-list"></div>`;

    // Chỉ vẽ lại phần danh sách khi gõ, để ô tìm kiếm và gợi ý không bị mất
    const listEl = $("#people-list");
    const drawList = () => {
      const q = norm(state.peopleQuery);
      listEl.innerHTML = listHtml(q);
      listEl.querySelectorAll("details.dept").forEach((d) => d.addEventListener("toggle", () => {
        if (q) return; // đang tìm kiếm thì các nhóm tự mở, không ghi nhớ
        d.open ? state.openDepts.add(d.dataset.dept) : state.openDepts.delete(d.dataset.dept);
      }));
      listEl.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => employeeForm(emps.find((e) => e.id == b.dataset.edit))));
    };
    drawList();

    // Tô đậm phần khớp; so khớp trên chuỗi không dấu nhưng hiển thị chuỗi gốc
    const hl = (text, ws) => {
      const chars = [...String(text ?? "")];
      let flat = "";
      const at = [];
      chars.forEach((c, i) => { const n = norm(c); flat += n; for (let k = 0; k < n.length; k++) at.push(i); });
      const on = new Array(chars.length).fill(false);
      ws.forEach((w) => {
        for (let p = flat.indexOf(w); p !== -1; p = flat.indexOf(w, p + 1))
          for (let k = p; k < p + w.length; k++) on[at[k]] = true;
      });
      let out = "";
      chars.forEach((c, i) => {
        if (on[i] && !on[i - 1]) out += "<mark>";
        out += esc(c);
        if (on[i] && !on[i + 1]) out += "</mark>";
      });
      return out;
    };
    // Ưu tiên: mã NV bắt đầu bằng → tên bắt đầu bằng → đầu một chữ trong tên → chứa trong mã/tên → chức danh
    const rank = (e, q, ws) => {
      const code = norm(e.employee_code), name = norm(e.full_name), title = norm(e.job_title || e.grade);
      if (code.startsWith(q)) return 0;
      if (name.startsWith(q)) return 1;
      if ((" " + name).includes(" " + q)) return 2;
      if (code.includes(q) || name.includes(q)) return 3;
      if ((" " + title).includes(" " + q)) return 4;
      if (title.includes(q)) return 5;
      return matchAll(e, ws) ? 6 : -1;
    };
    const MAX_SUGGEST = 10;
    const input = $("#people-q"), box = $("#people-suggest");
    let items = [], active = -1;

    const closeSuggest = () => { box.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; };
    const setActive = (i) => {
      active = i;
      box.querySelectorAll(".suggest-item").forEach((el, k) => el.classList.toggle("active", k === i));
      const el = box.querySelectorAll(".suggest-item")[i];
      if (el) el.scrollIntoView({ block: "nearest" });
    };
    const showSuggest = () => {
      const q = norm(input.value).trim().replace(/\s+/g, " ");
      if (!q) return closeSuggest();
      const ws = words(q);
      const found = emps.map((e) => ({ e, r: rank(e, q, ws) })).filter((x) => x.r >= 0)
        .sort((a, b) => a.r - b.r || a.e.full_name.localeCompare(b.e.full_name, "vi"));
      items = found.slice(0, MAX_SUGGEST).map((x) => x.e);
      box.innerHTML = items.length
        ? items.map((e, i) => `
            <div class="suggest-item" role="option" data-i="${i}">
              ${e.employee_code ? `<span class="badge">${hl(e.employee_code, ws)}</span>` : ""}
              <b>${hl(e.full_name, ws)}</b>
              <span class="sub muted">${hl(e.job_title || e.grade || "Nhân viên", ws)}${e.hr_department ? " – " + esc(e.hr_department) : ""}</span>
              ${e.status === "inactive" ? '<span class="badge warn">Đã nghỉ</span>' : ""}
            </div>`).join("")
          + (found.length > MAX_SUGGEST ? `<div class="suggest-more">và ${found.length - MAX_SUGGEST} người khác – xem danh sách bên dưới</div>` : "")
        : '<div class="suggest-more">Không có gợi ý phù hợp</div>';
      box.hidden = false;
      input.setAttribute("aria-expanded", "true");
      active = -1;
    };
    const pick = (e) => {
      closeSuggest();
      input.value = state.peopleQuery = e.full_name;
      state.peopleFocus = e.id;
      clearTimeout(input._t);
      drawList();
      const tr = listEl.querySelector(`tr[data-emp="${e.id}"]`);
      if (!tr) return;
      tr.scrollIntoView({ block: "center", behavior: "smooth" });
      tr.classList.remove("flash");
      void tr.offsetWidth; // chạy lại hiệu ứng nhấp nháy nếu chọn lại cùng người
      tr.classList.add("flash");
    };

    input.oninput = () => {
      state.peopleQuery = input.value;
      state.peopleFocus = null;
      showSuggest();
      clearTimeout(input._t);
      input._t = setTimeout(drawList, 200);
    };
    input.onfocus = () => { if (input.value.trim()) showSuggest(); };
    input.onblur = () => closeSuggest();
    input.onkeydown = (ev) => {
      if (ev.key === "Escape") return closeSuggest();
      if (box.hidden || !items.length) return;
      if (ev.key === "ArrowDown") { ev.preventDefault(); setActive((active + 1) % items.length); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); setActive((active - 1 + items.length) % items.length); }
      else if (ev.key === "Enter") { ev.preventDefault(); active >= 0 ? pick(items[active]) : closeSuggest(); }
    };
    box.onmousedown = (ev) => {
      ev.preventDefault(); // giữ focus ở ô tìm kiếm, không để blur đóng gợi ý trước khi chọn
      const el = ev.target.closest(".suggest-item");
      if (el) pick(items[el.dataset.i]);
    };
    box.onmousemove = (ev) => {
      const el = ev.target.closest(".suggest-item");
      if (el && +el.dataset.i !== active) setActive(+el.dataset.i);
    };

    $("#expand-all").onclick = () => { list.forEach((g) => state.openDepts.add(g.name)); render(); };
    $("#collapse-all").onclick = () => { state.openDepts.clear(); state.peopleQuery = ""; state.peopleFocus = null; render(); };
    $("#show-inactive").onchange = (e) => { state.showInactive = e.target.checked; render(); };
    if (canEditEmp) $("#add-emp").onclick = () => employeeForm({});
    if (canImport) $("#import-emp").onclick = () => openForm("Nhập danh sách nhân sự HCNS", [
      { name: "file", label: "File Excel danh sách nhân sự hiện hữu (.xlsx). Cập nhật theo mã NV; ai không còn trong file sẽ chuyển 'Đã nghỉ'.", type: "file", accept: ".xlsx,.xlsm", required: true },
    ], {}, async (d) => {
      const fd = new FormData();
      fd.append("file", d.file);
      const r = await api("/api/employees/import", { method: "POST", body: fd });
      toast(`Đã nhập ${r.total} nhân sự: thêm mới ${r.created}, cập nhật ${r.updated}, chuyển 'Đã nghỉ' ${r.inactive}.`
        + (r.created_units.length ? ` Tạo thêm đơn vị: ${r.created_units.join(", ")}` : ""));
    });
  },

  async insights(main) {
    const ins = await api("/api/insights");
    const unitLink = (id, name) => `<button class="link" onclick="go('units',{unitId:${id}})">${esc(name)}</button>`;
    const block = (title, items, fmt, note) => `
      <div class="card insight">
        <h3>${title} <span class="badge">${items.length}</span></h3>
        ${note ? `<p class="muted">${note}</p>` : ""}
        ${items.length ? `<ul>${items.map(fmt).join("")}</ul>` : '<div class="empty">Không có</div>'}
      </div>`;
    main.innerHTML = `
      <div class="page-head"><div><h2>Phân tích cơ cấu tổ chức</h2>
        <p>Các chỉ dấu dưới đây được tính trực tiếp từ dữ liệu, chưa phải kết luận. Hỏi Trợ lý AI để có đánh giá và đề xuất.</p></div>
        ${canSee("chat") ? `<button class="primary accent" onclick="go('chat')">${icon("spark")} Hỏi Trợ lý AI</button>` : ""}</div>
      <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(340px, 1fr))">
        ${block("Người kiêm nhiệm nhiều đơn vị", ins.concurrent_roles, (x) => `<li><b>${esc(x.name)}</b>: ${x.roles.map(esc).join("; ")}</li>`,
          "Kiêm nhiệm giúp tiết kiệm chi phí nhưng tạo rủi ro quá tải và xung đột lợi ích (đặc biệt kiểm soát nội bộ vs tài chính).")}
        ${block("Vị trí đang trống (TBA)", ins.vacancies, (x) => `<li>${esc(x.title)} – ${unitLink(x.unit_id, x.unit_name)}</li>`)}
        ${block("Phòng/ban do cấp phó phụ trách", ins.deputy_led_departments, (x) => `<li>${unitLink(x.unit_id, x.unit_name)} – ${esc(x.title)} ${esc(x.name || "TBA")}</li>`,
          "Chưa có Trưởng phòng – cân nhắc bổ nhiệm hoặc xác nhận đây là chủ trương.")}
        ${block("Tầm hạn quản lý (số đơn vị trực tiếp)", ins.span_of_control, (x) => `<li>${unitLink(x.unit_id, x.unit_name)}: <b>${x.direct_reports}</b></li>`)}
        ${block("Phòng/ban chưa có quy trình", ins.units_without_process, (x) => `<li>${unitLink(x.unit_id, x.unit_name)}</li>`)}
        ${block("Dữ liệu cần xác nhận", [...ins.unverified.units.map((u) => ({ ...u, k: "u" })), ...ins.unverified.employees.map((e) => ({ ...e, k: "e" }))],
          (x) => (x.k === "u" ? `<li>${unitLink(x.id, x.name)}: ${esc(x.full_name || "")}</li>` : `<li>Nhân sự: ${esc(x.full_name)}</li>`))}
      </div>`;
  },

  async docs(main) {
    const [docs, meta, units] = await Promise.all([api("/api/documents"), api("/api/documents/meta"), api("/api/units")]);
    main.innerHTML = `
      <div class="toolbar"><h2 style="margin:0">Kho tài liệu (${docs.length})</h2>
        ${can("docs_edit") ? DOC_ACTIONS : ""}</div>
      <p class="muted">Quy trình ISO, hướng dẫn, biểu mẫu, quy định... Hỗ trợ ${meta.allowed_ext.join(", ")} (tối đa ${meta.max_mb} MB).
        PDF scan được đọc bằng AI ${meta.ocr_available ? "" : '<span class="badge warn">cần khoá Gemini API</span>'}.</p>
      ${(() => {
        const unread = docs.filter((d) => DOC_UNREAD.has(d.extract_status));
        return unread.length ? `<div class="unread-banner">⚠ <b>${unread.length} tài liệu chưa đọc được</b> – trợ lý AI chưa trả lời được từ nội dung các file này:
          ${unread.slice(0, 5).map((d) => `<b>${esc((d.code || d.title).slice(0, 60))}</b>`).join(", ")}${unread.length > 5 ? "…" : ""}
          <button class="link" id="doc-show-unread">Chỉ hiện các file này</button></div>` : "";
      })()}
      <div class="card" style="margin-bottom:16px">
        <form id="doc-search" class="chat-input" style="margin:0">
          <input name="q" autocomplete="off" placeholder="Tìm trong nội dung tài liệu (không cần gõ dấu)..." value="${esc(state.docQuery)}"
                 style="flex:1;padding:8px;border:1px solid var(--line);border-radius:8px">
          <button class="primary">Tìm</button>
        </form>
        <div class="doc-filters" id="doc-filters">
          <select name="unit"><option value="">Tất cả đơn vị</option><option value="none">Tài liệu chung</option>
            ${[...new Map(docs.filter((d) => d.unit_id).map((d) => [d.unit_id, d.unit_name])).entries()].sort((a, b) => a[1].localeCompare(b[1], "vi"))
              .map(([id, n]) => `<option value="${id}">${esc(n)}</option>`).join("")}</select>
          <select name="type"><option value="">Tất cả loại</option>
            ${Object.entries(DOC_LABELS).filter(([k]) => docs.some((d) => d.doc_type === k)).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select>
          <select name="status"><option value="">Mọi trạng thái</option>
            ${docs.some((d) => DOC_UNREAD.has(d.extract_status)) ? '<option value="unread">⚠ Chưa đọc được</option>' : ""}
            ${Object.entries(DOC_STATUS).filter(([k]) => docs.some((d) => d.extract_status === k)).map(([k, v]) => `<option value="${k}">${esc(v[0])}</option>`).join("")}</select>
          <button type="button" class="link" id="doc-filter-reset" hidden>✕ Bỏ lọc</button>
          <span class="muted" id="doc-filter-count"></span>
        </div>
        <div id="doc-hits"></div>
      </div>
      <div class="card ${state.user.role === "viewer" ? "readonly" : ""}" id="doc-all"></div>`;
    const F = (state.docFilter ||= { unit: "", type: "", status: "" });
    const filt = (list) => list.filter((d) =>
      (!F.unit || (F.unit === "none" ? !d.unit_id : String(d.unit_id) === F.unit)) &&
      (!F.type || d.doc_type === F.type) &&
      (!F.status || (F.status === "unread" ? DOC_UNREAD.has(d.extract_status) : d.extract_status === F.status)));
    const filtering = () => !!(F.unit || F.type || F.status);
    const renderAll = () => {
      const list = filt(docs);
      $("#doc-all").innerHTML = list.length ? docTable(list, true) : '<div class="empty">Không có tài liệu nào khớp bộ lọc.</div>';
      $("#doc-filter-reset").hidden = !filtering();
      $("#doc-filter-count").textContent = filtering() && !state.docQuery.trim() ? `${list.length}/${docs.length} tài liệu` : "";
      if (!$("#doc-all").hidden) bindDocActions($("#doc-all"), meta, units);
    };
    const showUnreadBtn = $("#doc-show-unread");
    if (showUnreadBtn) showUnreadBtn.onclick = () => { F.status = "unread"; document.querySelector('#doc-filters select[name="status"]').value = "unread"; renderAll(); };
    document.querySelectorAll("#doc-filters select").forEach((sel) => {
      sel.value = F[sel.name];
      sel.onchange = () => { F[sel.name] = sel.value; renderAll(); showHits(); };
    });
    $("#doc-filter-reset").onclick = () => {
      Object.assign(F, { unit: "", type: "", status: "" });
      document.querySelectorAll("#doc-filters select").forEach((x) => (x.value = ""));
      renderAll(); showHits();
    };
    $("#up-doc")?.addEventListener("click", () => uploadForm(meta, units, null));
    $("#url-doc")?.addEventListener("click", () => urlLearnForm(units, null));
    // Đang tìm kiếm: chỉ hiện kết quả, ẩn danh sách đầy đủ để khỏi trùng lặp.
    let seq = 0; // bỏ qua kết quả của lần gõ cũ nếu về muộn
    const showHits = async () => {
      const q = state.docQuery.trim();
      const my = ++seq;
      $("#doc-all").hidden = !!q;
      if (!q) return ($("#doc-hits").innerHTML = "");
      if (!$("#doc-hits").innerHTML) $("#doc-hits").innerHTML = '<div class="muted" style="margin-top:10px">Đang tìm…</div>';
      const hits = filt(await api(`/api/documents/search?q=${encodeURIComponent(q)}`));
      if (my !== seq) return;
      $("#doc-hits").innerHTML = `
        <div class="toolbar" style="margin:10px 0 0">
          <span class="muted">${hits.length ? `Tìm thấy ${hits.length} tài liệu cho “${esc(q)}”.` : `Không tìm thấy tài liệu nào phù hợp với “${esc(q)}”.`}</span>
          <button type="button" class="link" id="doc-clear">✕ Xoá tìm kiếm</button>
        </div>
        ${hits.length ? docTable(hits, true, q) : ""}`;
      $("#doc-clear").onclick = () => { state.docQuery = ""; $("#doc-search").elements.q.value = ""; showHits(); };
      bindDocActions($("#doc-hits"), meta, units);
    };
    // Enter / nút Tìm: tìm ngay. Gõ: tìm sau 300ms, từ 2 ký tự; xoá hết thì về danh sách đầy đủ.
    $("#doc-search").onsubmit = (e) => {
      e.preventDefault();
      clearTimeout(e.target._t);
      state.docQuery = e.target.elements.q.value;
      showHits();
    };
    const qInput = $("#doc-search").elements.q;
    qInput.oninput = () => {
      const form = $("#doc-search");
      clearTimeout(form._t);
      const v = qInput.value.trim();
      if (v.length === 1) return;
      form._t = setTimeout(() => { state.docQuery = qInput.value; showHits(); }, v ? 80 : 0);
    };
    renderAll();
    showHits();
    bindDocActions(main, meta, units);
    pollIfProcessing(docs);
  },

  async users(main) {
    const [users, units] = await Promise.all([api("/api/users"), api("/api/units")]);
    main.innerHTML = `
      <div class="toolbar"><h2 style="margin:0">Tài khoản (${users.length})</h2><button class="primary" id="add-user">+ Tạo tài khoản</button></div>
      <div class="card">
        <table>
          <tr><th>Tên đăng nhập</th><th>Họ tên</th><th>Hồ sơ nhân sự</th><th>Vai trò</th><th>Đơn vị phụ trách</th><th>Quyền cấp thêm</th><th>Dung lượng riêng</th><th>Trạng thái</th><th></th></tr>
          ${users.map((x) => `<tr><td>${esc(x.username)}</td><td>${esc(x.full_name || "")}</td><td>${x.employee_name ? esc(x.employee_name) : '<span class="badge warn">Chưa gán</span>'}</td><td>${esc(state.roles[x.role])}</td>
            <td>${esc(x.unit_name || "—")}</td><td>${["admin", "ceo"].includes(x.role) ? '<span class="muted">Mặc định có đủ</span>' : (x.granted.map((f) => esc(FEATURE_LABELS[f])).join(", ") || '<span class="muted">—</span>')}</td><td>${["admin", "ceo"].includes(x.role) ? '<span class="muted">Không giới hạn</span>' : `${fmtSize(x.private_bytes) || "0 KB"} / ${x.quota_mb || 300} MB`}</td><td>${x.active ? '<span class="badge ok">Hoạt động</span>' : '<span class="badge warn">Đã khoá</span>'}${x.locked ? ' <span class="badge warn">Sai mật khẩu nhiều lần</span>' : ""}</td>
            <td><button class="link" data-edit="${x.id}">Sửa</button> · <button class="link" data-link="${x.id}">Gán hồ sơ</button>${["admin", "ceo"].includes(x.role) ? "" : ` · <button class="link" data-perm="${x.id}">Cấp quyền</button>`}${x.role === "viewer" ? "" : ` · <button class="link" data-mem="${x.id}">Ghi chú AI</button>`}${x.locked ? ` · <button class="link" data-unlock="${x.id}">Mở khoá đăng nhập</button>` : ""}</td></tr>`).join("")}
        </table>
      </div>
      <div class="card" style="margin-top:16px">
        <h3>Phân quyền</h3>
        <table>
          <tr><th>Vai trò</th><th>Xem</th><th>Chỉnh sửa</th><th>Trợ lý AI</th></tr>
          <tr><td colspan="4" class="muted">Tài liệu, Phân tích và Nhập file HCNS: chỉ admin/Ban TGĐ mặc định có; các tài khoản khác cần được cấp ở nút "Cấp quyền".</td></tr>
          <tr><td>Quản trị hệ thống</td><td>Tất cả</td><td>Tất cả + tài khoản</td><td>Có</td></tr>
          <tr><td>Ban Tổng Giám đốc</td><td>Tất cả</td><td>Tất cả</td><td>Có</td></tr>
          <tr><td>Quản lý đơn vị</td><td>Sơ đồ, phòng ban, nhân sự</td><td>Đơn vị mình + đơn vị con: chức danh, quy trình, mục tiêu (tài liệu: cần được cấp)</td><td>Không</td></tr>
          <tr><td>Chỉ xem</td><td>Sơ đồ, phòng ban, nhân sự</td><td>Không</td><td>Không</td></tr>
        </table>
      </div>`;
    const form = (x, free = []) => openForm(x.id ? `Sửa tài khoản ${x.username}` : "Tạo tài khoản", [
      ...(x.id ? [] : [{ name: "username", label: "Tên đăng nhập", required: true }]),
      { name: "full_name", label: "Họ tên" },
      ...(x.id ? [] : [{ name: "employee_id", label: "Hồ sơ nhân sự (có thể bỏ qua: người dùng tự xin liên kết sau, bạn chỉ cần duyệt)", type: "select", numeric: true, search: true,
        options: [["", "— Bỏ qua, gán sau —"], ...free.map((e) => [e.id, `${e.full_name}${e.job_title ? " – " + e.job_title : ""}${e.unit_name ? " (" + e.unit_name + ")" : ""}`])] }]),
      { name: "role", label: "Vai trò", type: "select", options: Object.entries(state.roles), default: "viewer" },
      ...(x.id ? [] : [{ ...tplField, label: "Mẫu quyền cấp thêm (Quản lý / Chỉ xem)" }]),
      { name: "unit_id", label: "Đơn vị phụ trách (cho vai trò Quản lý đơn vị)", type: "select", numeric: true, options: [["", "— Không —"], ...units.map((u) => [u.id, u.name])] },
      ...(x.id ? [{ name: "active", label: "Trạng thái", type: "select", numeric: true, options: [[1, "Hoạt động"], [0, "Khoá"]] },
        { name: "quota_mb", label: "Hạn mức dung lượng dữ liệu riêng (MB; để trống = mặc định 300 MB)", type: "number", numeric: true }] : []),
      { name: "password", label: x.id ? "Đặt lại mật khẩu (để trống nếu không đổi)" : "Mật khẩu (tối thiểu 8 ký tự)", type: "password", required: !x.id },
    ], x, (d) => {
      const { _tpl, ...body } = d;
      return x.id ? api(`/api/users/${x.id}`, { method: "PUT", body }) : api("/api/users", { method: "POST", body: { ...body, features: (PERM_TEMPLATES[_tpl] || [])[1] || [] } });
    });
    $("#add-user").onclick = async () => {
      try {
        const opt = await api("/api/employee-links");
        form({}, opt.employees.filter((e) => !e.linked_user_id));
      } catch (e) { toast(e.message, "err"); }
    };
    api("/api/link-requests").then((reqs) => {
      if (!reqs.length) return;
      main.insertAdjacentHTML("afterbegin", `<div class="card" id="link-requests" style="margin-bottom:16px">
        <h3>Yêu cầu liên kết hồ sơ nhân sự (${reqs.length} chờ duyệt)</h3>
        <p class="muted">Người dùng tự chọn hồ sơ của mình. Kiểm tra đúng người rồi duyệt: tài khoản sẽ xem được thông tin cá nhân của hồ sơ đó.</p>
        <table><tr><th>Tài khoản</th><th>Xin liên kết với hồ sơ</th><th>Gửi lúc</th><th></th></tr>
          ${reqs.map((r) => `<tr><td><b>${esc(r.username)}</b><div class="muted small">${esc(r.user_name || "")}</div></td>
            <td><b>${esc(r.employee_name)}</b><div class="muted small">${esc([r.job_title, r.unit_name].filter(Boolean).join(" – "))}</div></td>
            <td class="muted">${esc((r.created_at || "").slice(0, 16))}</td>
            <td style="white-space:nowrap"><button class="link" data-lk-ok="${r.id}">Duyệt</button> · <button class="link danger" data-lk-no="${r.id}">Từ chối</button></td></tr>`).join("")}
        </table></div>`);
      const decide = async (id, approve) => {
        let note = "";
        if (!approve) { note = await ask({ title: "Từ chối yêu cầu", message: "Ghi lý do để người dùng biết (không bắt buộc).", input: "", okText: "Từ chối" }); if (note === null) return; }
        try { await api(`/api/link-requests/${id}/decide`, { method: "POST", body: { approve, note } }); toast(approve ? "Đã liên kết tài khoản với hồ sơ." : "Đã từ chối."); refreshPending(); render(); } catch (e) { toast(e.message, "err"); }
      };
      $("#link-requests").querySelectorAll("[data-lk-ok]").forEach((b) => (b.onclick = () => decide(b.dataset.lkOk, true)));
      $("#link-requests").querySelectorAll("[data-lk-no]").forEach((b) => (b.onclick = () => decide(b.dataset.lkNo, false)));
    }).catch(() => {});
    main.querySelectorAll("[data-unlock]").forEach((b) => (b.onclick = async () => {
      try { await api(`/api/users/${b.dataset.unlock}/unlock`, { method: "POST" }); render(); } catch (e) { toast(e.message, "err"); }
    }));
    main.querySelectorAll("[data-perm]").forEach((b) => (b.onclick = () => {
      const x = users.find((y) => y.id == b.dataset.perm);
      const checked = (f) => (f === "docs_view" && x.granted.includes("docs_edit")) || x.granted.includes(f);
      openForm(`Cấp quyền cho ${x.username}`, [tplField, ...Object.entries(FEATURE_LABELS).map(([f, l]) => ({
        name: f, label: l, type: "select", numeric: true, options: [[0, "Không"], [1, "Được dùng"]], default: checked(f) ? 1 : 0,
      }))], Object.fromEntries(Object.keys(FEATURE_LABELS).map((f) => [f, checked(f) ? 1 : 0])),
      (d) => api(`/api/users/${x.id}/permissions`, { method: "PUT", body: { features: Object.keys(FEATURE_LABELS).filter((f) => Number(d[f]) === 1) } }));
      $("#modal-form").elements._tpl.onchange = (e) => {
        const on = PERM_TEMPLATES[e.target.value][1];
        Object.keys(FEATURE_LABELS).forEach((f) => ($("#modal-form").elements[f].value = on.includes(f) ? 1 : 0));
      };
    }));
    main.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(users.find((x) => x.id == b.dataset.edit))));
    main.querySelectorAll("[data-link]").forEach((b) => (b.onclick = async () => {
      const x = users.find((y) => y.id == b.dataset.link);
      try {
        const opt = await api("/api/employee-links");
        const sug = opt.suggestions[x.id];
        const label = (e) => `${e.full_name}${e.job_title ? " – " + e.job_title : ""}${e.unit_name ? " (" + e.unit_name + ")" : ""}${e.linked_user_id && e.linked_user_id !== x.id ? " [đã gán cho tài khoản khác]" : ""}`;
        openForm(`Gán hồ sơ nhân sự cho ${x.username}`, [
          { type: "info", label: sug ? `Gợi ý: họ tên trùng khớp với "${opt.employees.find((e) => e.id === sug)?.full_name}". Kiểm tra đúng người rồi bấm Lưu.`
            : "Không có gợi ý tự động (họ tên tài khoản không khớp hoặc trùng nhiều người). Chọn đúng nhân viên, tránh gán nhầm vì tài khoản sẽ xem được thông tin cá nhân của hồ sơ đó." },
          { name: "employee_id", label: "Nhân viên", type: "select", numeric: true, search: true, default: x.employee_id || sug || "",
            options: [["", "— Không gán —"], ...opt.employees.map((e) => [e.id, label(e)])] },
        ], { employee_id: x.employee_id }, (d) => api(`/api/users/${x.id}/employee`, { method: "PUT", body: { employee_id: d.employee_id } }));
      } catch (e) { toast(e.message, "err"); }
    }));
    api("/api/employee-requests").then((reqs) => {
      if (!reqs.length) return;
      const FL = { full_name: "Họ tên", phone: "Số điện thoại", email: "Email", birth_date: "Ngày sinh", joined_date: "Ngày vào công ty", job_title: "Chức danh", contract_term: "Loại hợp đồng" };
      const fmt = (f, v) => (/_date$/.test(f) && /^\d{4}-\d{2}-\d{2}$/.test(v || "") ? v.split("-").reverse().join("/") : v || "—");
      main.insertAdjacentHTML("afterbegin", `<div class="card" id="emp-requests" style="margin-bottom:16px">
        <h3>Yêu cầu sửa hồ sơ nhân sự (${reqs.length} chờ duyệt)</h3>
        <p class="muted">Do chính nhân viên gửi cho hồ sơ của mình. Chỉ ghi vào danh sách nhân sự khi bạn duyệt; giá trị cũ được lưu trong nhật ký. Lưu ý: nếu sau này nhập lại file HCNS, dữ liệu trong file có thể ghi đè giá trị đã sửa, nên hãy sửa cả file gốc.</p>
        <table><tr><th>Nhân viên</th><th>Thông tin</th><th>Hiện tại</th><th>Đề nghị</th><th>Ghi chú</th><th></th></tr>
          ${reqs.map((r) => `<tr><td><b>${esc(r.employee_name)}</b><div class="muted small">tài khoản ${esc(r.username)} · ${esc((r.created_at || "").slice(0, 16))}</div></td>
            <td>${esc(FL[r.field] || r.field)}</td><td class="muted">${esc(fmt(r.field, r.old_value))}</td><td><b>${esc(fmt(r.field, r.new_value))}</b></td>
            <td class="muted">${esc(r.reason || "")}</td>
            <td style="white-space:nowrap"><button class="link" data-emp-ok="${r.id}">Duyệt</button> · <button class="link danger" data-emp-no="${r.id}">Từ chối</button></td></tr>`).join("")}
        </table></div>`);
      const decide = async (id, approve) => {
        let note = "";
        if (!approve) { note = await ask({ title: "Từ chối yêu cầu", message: "Ghi lý do để nhân viên biết (không bắt buộc).", input: "", okText: "Từ chối" }); if (note === null) return; }
        try { await api(`/api/employee-requests/${id}/decide`, { method: "POST", body: { approve, note } }); toast(approve ? "Đã cập nhật hồ sơ." : "Đã từ chối."); render(); } catch (e) { toast(e.message, "err"); }
      };
      $("#emp-requests").querySelectorAll("[data-emp-ok]").forEach((b) => (b.onclick = () => decide(b.dataset.empOk, true)));
      $("#emp-requests").querySelectorAll("[data-emp-no]").forEach((b) => (b.onclick = () => decide(b.dataset.empNo, false)));
    }).catch(() => {});
    main.querySelectorAll("[data-mem]").forEach((b) => (b.onclick = async () => {
      try {
        const r = await api(`/api/admin/memory?user_id=${b.dataset.mem}`);
        $("#modal-title").textContent = `Ghi chú AI về ${r.user.full_name || r.user.username} (${r.enabled ? "đang bật" : "đang tắt"})`;
        $("#modal-body").innerHTML = r.notes.length ? `<table>${r.notes.map((n) => `<tr><td>${esc(n.text)}<div class="muted small">${n.active ? "Đang dùng" : "Chưa dùng"} · ${esc((n.updated_at || "").slice(0, 16))}</div></td></tr>`).join("")}</table>` : '<div class="empty">Chưa có ghi chú nào.</div>';
        $("#modal-form").onsubmit = (e) => { e.preventDefault(); $("#modal").close(); };
        $("#modal-cancel").onclick = () => $("#modal").close();
        $("#modal").showModal();
      } catch (e) { toast(e.message, "err"); }
    }));
    api("/api/admin/offboarding").then((o) => {
      if (!o.accounts.length) return;
      main.insertAdjacentHTML("beforeend", `<div class="card" id="offboarding" style="margin-top:16px">
        <h3>Dữ liệu của tài khoản đã khoá (nghỉ việc)</h3>
        <p class="muted">Dữ liệu riêng (file đính kèm chat, ghi chú AI, lịch sử chat) được giữ ${o.retention_days} ngày kể từ lúc khoá để bàn giao. Đến hạn, chỉ khi bạn duyệt thì mới xoá vĩnh viễn; mở khoá lại tài khoản sẽ huỷ đồng hồ. Tài liệu đã đưa lên thư viện chung không bị xoá.</p>
        <table><tr><th>Tài khoản</th><th>Khoá từ</th><th>Thời hạn giữ</th><th>Dữ liệu</th><th></th></tr>
          ${o.accounts.map((a) => `<tr><td><b>${esc(a.full_name || a.username)}</b><div class="muted small">${esc(a.username)}</div></td>
            <td class="muted">${esc((a.deactivated_at || "").slice(0, 10))}</td>
            <td>${a.due ? '<span class="badge warn">Đến hạn, chờ bạn duyệt xoá</span>' : `<span class="badge ok">Còn ${a.days_left} ngày</span>`}</td>
            <td>${a.files} file (${fmtSize(a.bytes) || "0 KB"}) · ${a.notes} ghi chú AI · ${a.conversations} đoạn chat</td>
            <td style="white-space:nowrap">${a.files ? `<button class="link" data-off-view="${a.id}" data-name="${esc(a.full_name || a.username)}">Xem file</button> · ` : ""}${a.due ? `<button class="link danger" data-off-purge="${a.id}" data-user="${esc(a.username)}">Duyệt xoá dữ liệu</button>` : '<span class="muted small">Chưa đến hạn</span>'}</td></tr>`).join("")}
        </table></div>`);
      const box = $("#offboarding");
      box.querySelectorAll("[data-off-view]").forEach((b) => (b.onclick = async () => {
        const files = await api(`/api/admin/private-files?user_id=${b.dataset.offView}`);
        $("#modal-title").textContent = `File riêng: ${b.dataset.name}`;
        $("#modal-body").innerHTML = `<table><tr><th>Tệp</th><th>Dung lượng</th><th></th></tr>${files.map((f) => `<tr><td>${esc(f.filename)}</td><td>${fmtSize(f.size_bytes)}</td><td><a class="link" href="/api/my-files/${f.id}/file" target="_blank">Tải về</a></td></tr>`).join("")}</table>`;
        $("#modal-form").onsubmit = (e) => { e.preventDefault(); $("#modal").close(); };
        $("#modal-cancel").onclick = () => $("#modal").close();
        $("#modal").showModal();
      }));
      box.querySelectorAll("[data-off-purge]").forEach((b) => (b.onclick = async () => {
        const typed = await ask({ title: `Xoá vĩnh viễn dữ liệu của ${b.dataset.user}?`, message: "Toàn bộ file riêng, ghi chú AI và lịch sử chat của tài khoản này sẽ bị xoá, không thể khôi phục. Gõ lại tên đăng nhập để xác nhận.", input: "", okText: "Xoá vĩnh viễn", danger: true });
        if (!typed) return;
        try {
          const r = await api(`/api/admin/offboarding/${b.dataset.offPurge}/purge`, { method: "POST", body: { confirm: typed } });
          toast(`Đã xoá ${r.files} file, ${r.notes} ghi chú, ${r.conversations} đoạn chat.`);
          render();
        } catch (e) { toast(e.message, "err"); }
      }));
    }).catch(() => {});
  },

  async myfiles(main) {
    const [data, meta] = await Promise.all([api("/api/my-files"), api("/api/my-files/meta")]);
    const isExec = !!state.user.edit_all;
    const owners = isExec ? await api("/api/admin/private-files") : [];
    const orphan = isExec ? await api("/api/admin/private-files?user_id=0") : [];
    const u = data.usage;
    const bar = u.quota_mb == null
      ? `<div class="quota-text">Đã dùng <b>${u.used_mb} MB</b> · không giới hạn dung lượng</div>`
      : `<div class="quota-text">Đã dùng <b>${u.used_mb} MB</b> / ${u.quota_mb} MB · còn <b>${u.remaining_mb} MB</b></div>
         <div class="quota-bar ${u.percent >= 90 ? "warn" : ""}"><i style="width:${u.percent}%"></i></div>`;
    const STATUS = { pending: ["Đang xử lý", "warn"], processing: ["Đang đọc...", "warn"], ok: ["Đã đọc", "ok"],
      needs_ocr: ["Chờ đọc khi bạn gửi câu hỏi", "warn"], failed: ["Chưa đọc được", "bad"] };
    const fileRows = (files, own) => files.map((d) => {
      const [lbl, cls] = STATUS[d.extract_status] || [d.extract_status, ""];
      return `<tr${d.extract_status === "failed" ? ' class="row-bad"' : ""}>
        <td><b>${esc(d.title)}</b><div class="muted">${esc(d.filename)} · ${fmtSize(d.size_bytes)}</div>
          ${d.extract_note && d.extract_status !== "needs_ocr" ? `<div style="color:var(--${d.extract_status === "failed" ? "danger" : "warn"})">${esc(d.extract_note)}</div>` : ""}</td>
        <td><span class="badge ${cls}">${lbl}</span></td>
        <td class="muted">${esc((d.uploaded_at || "").slice(0, 16))}</td>
        <td style="white-space:nowrap">
          <button class="link" data-mf-view="${d.id}">Xem chữ</button> ·
          <a class="link" href="/api/my-files/${d.id}/file" target="_blank">Tải về</a>
          ${own && ["needs_ocr", "failed"].includes(d.extract_status) ? ` · <button class="link" data-mf-read="${d.id}">${d.extract_status === "failed" ? "Đọc lại" : "Đọc ngay"}</button>` : ""}
          ${own && d.extract_status === "ok" && can("docs_edit") ? ` · <button class="link" data-mf-pub="${d.id}">Đưa lên thư viện chung</button>` : ""}
          · <button class="link danger" data-mf-del="${d.id}">Xoá</button></td></tr>`;
    }).join("");
    main.innerHTML = `
      <div class="card">
        <h3>Dữ liệu của tôi</h3>
        <p class="muted">File và ảnh bạn đính kèm khi chat. Chúng nằm ở kho riêng của tài khoản bạn, không lẫn vào thư viện tài liệu chung;
          người dùng khác và trợ lý AI của họ không thấy. Ảnh, bản scan và ghi âm chỉ được AI đọc khi bạn gửi câu hỏi
          (tối đa ${esc(String(meta.ocr_daily_limit))} lượt mỗi ngày).</p>
        ${bar}
      </div>
      <div class="card" style="margin-top:16px">
        ${data.files.length ? `<table><tr><th>Tệp</th><th>Trạng thái</th><th>Tải lên</th><th></th></tr>${fileRows(data.files, true)}</table>`
          : '<div class="empty">Chưa có file nào. Đính kèm file hoặc dán ảnh (Ctrl+V) trong khung chat để bắt đầu.</div>'}
      </div>
      ${isExec ? `<div class="card" style="margin-top:16px">
        <h3>Kho riêng của các tài khoản</h3>
        <table><tr><th>Tài khoản</th><th>Số file</th><th>Đã dùng</th><th>Hạn mức</th><th></th></tr>
          ${owners.filter((o) => o.files).map((o) => `<tr><td><b>${esc(o.full_name || o.username)}</b><div class="muted small">${esc(o.username)}</div></td>
            <td>${o.files}</td><td>${fmtSize(o.used_bytes) || "0 KB"}</td>
            <td>${["admin", "ceo"].includes(o.role) ? "Không giới hạn" : `${o.quota_mb || 300} MB`}</td>
            <td><button class="link" data-mf-owner="${o.user_id}" data-name="${esc(o.full_name || o.username)}">Xem file</button></td></tr>`).join("") || '<tr><td colspan="5" class="muted">Chưa có tài khoản nào lưu file riêng.</td></tr>'}
          ${orphan.length ? `<tr><td><b>Chưa rõ chủ (chờ xử lý)</b></td><td>${orphan.length}</td><td>${fmtSize(orphan.reduce((a, d) => a + (d.size_bytes || 0), 0))}</td><td></td>
            <td><button class="link" data-mf-owner="0" data-name="Chưa rõ chủ">Xem file</button></td></tr>` : ""}
        </table>
        <p class="muted small">Nâng hạn mức cho từng người ở mục Tài khoản → Sửa.</p>
      </div>` : ""}`;
    pollIfProcessing(data.files);
    const showText = async (id) => {
      const d = await api(`/api/my-files/${id}`);
      $("#modal-title").textContent = d.title;
      $("#modal-body").innerHTML = `<p class="muted">Nội dung AI sẽ đọc (${fmtNum(d.char_count)} ký tự)</p>
        <div class="process-content" style="max-height:60vh;overflow:auto">${esc(d.content || "Chưa có nội dung – file chưa được đọc xong hoặc bị lỗi.")}</div>`;
      $("#modal-form").onsubmit = (e) => { e.preventDefault(); $("#modal").close(); };
      $("#modal-cancel").onclick = () => $("#modal").close();
      $("#modal").showModal();
    };
    const del = async (id) => {
      if (!(await confirmBox("Xoá file này?", "File và nội dung đã đọc sẽ bị xoá khỏi kho riêng, trợ lý AI không còn tra cứu được.", { okText: "Xoá", danger: true }))) return;
      try { await api(`/api/my-files/${id}`, { method: "DELETE" }); toast("Đã xoá."); $("#modal").open && $("#modal").close(); render(); } catch (e) { toast(e.message, "err"); }
    };
    const bindRows = (el) => {
      el.querySelectorAll("[data-mf-view]").forEach((b) => (b.onclick = () => showText(b.dataset.mfView).catch((e) => toast(e.message, "err"))));
      el.querySelectorAll("[data-mf-del]").forEach((b) => (b.onclick = () => del(b.dataset.mfDel)));
    };
    bindRows(main);
    main.querySelectorAll("[data-mf-read]").forEach((b) => (b.onclick = async () => {
      b.disabled = true;
      b.textContent = "Đang đọc...";
      try {
        const r = await api(`/api/my-files/${b.dataset.mfRead}/read`, { method: "POST" });
        if (r.extract_status !== "ok") toast(r.extract_note || "Chưa đọc được file này.", "err");
      } catch (e) { toast(e.message, "err"); }
      render();
    }));
    main.querySelectorAll("[data-mf-pub]").forEach((b) => (b.onclick = async () => {
      const [units, docMeta] = await Promise.all([api("/api/units"), api("/api/documents/meta")]);
      const f = data.files.find((x) => x.id == b.dataset.mfPub);
      openForm("Đưa lên thư viện chung", [
        { name: "title", label: "Tên tài liệu", required: true },
        { name: "unit_id", label: "Đơn vị chủ quản", type: "select", numeric: true, options: [["", "— Tài liệu chung công ty —"], ...units.map((x) => [x.id, x.name])] },
        { name: "access_level", label: "Độ mật (ai được xem, kể cả qua trợ lý AI)", type: "select", options: docMeta.levels, default: docMeta.default_level },
      ], { title: f.title }, (d) => api(`/api/my-files/${f.id}/publish`, { method: "POST", body: d }).then(() => toast("Đã đưa một bản sao lên thư viện chung.")), "Đưa lên");
    }));
    main.querySelectorAll("[data-mf-owner]").forEach((b) => (b.onclick = async () => {
      const files = await api(`/api/admin/private-files?user_id=${b.dataset.mfOwner}`);
      $("#modal-title").textContent = `File riêng: ${b.dataset.name}`;
      $("#modal-body").innerHTML = `<table><tr><th>Tệp</th><th>Trạng thái</th><th>Tải lên</th><th></th></tr>${fileRows(files, false)}</table>`;
      bindRows($("#modal-body"));
      $("#modal-form").onsubmit = (e) => { e.preventDefault(); $("#modal").close(); };
      $("#modal-cancel").onclick = () => $("#modal").close();
      $("#modal").showModal();
    }));
  },

  async profile(main) {
    const data = await api("/api/me/profile");
    const p = data.profile;
    const lr = data.link_request;
    const RSTATUS = { pending: ["Chờ duyệt", "warn"], approved: ["Đã duyệt", "ok"], rejected: ["Từ chối", "warn"] };
    const fmtVal = (f, v) => (/_date$/.test(f) && /^\d{4}-\d{2}-\d{2}$/.test(v || "") ? v.split("-").reverse().join("/") : v || "");
    const rows = p ? [["Họ tên", "full_name"], ["Mã nhân viên"], ["Chức danh", "job_title"], ["Đơn vị", null, p.unit_name || p.hr_department],
      ["Số điện thoại", "phone"], ["Email", "email"], ["Ngày sinh", "birth_date"], ["Ngày vào công ty", "joined_date"], ["Loại hợp đồng", "contract_term"]] : [];
    const ln = data.link_notice;
    const newResults = data.requests.filter((r) => r.status !== "pending" && r.seen_by_user === 0);
    const notice = ln ? (ln.status === "approved"
      ? `<div class="card" style="margin-bottom:16px;border-color:var(--ok)"><b style="color:var(--ok)">Đã liên kết hồ sơ.</b> Quản trị viên đã duyệt: tài khoản của bạn gắn với hồ sơ <b>${esc(ln.employee_name)}</b>. Trợ lý AI giờ trả lời được "thông tin của tôi".</div>`
      : `<div class="card" style="margin-bottom:16px;border-color:var(--warn)"><b style="color:var(--warn)">Yêu cầu liên kết bị từ chối.</b> Hồ sơ <b>${esc(ln.employee_name)}</b>${ln.admin_note ? ` — lý do: ${esc(ln.admin_note)}` : "."} Bạn có thể chọn lại hồ sơ khác.</div>`)
      : newResults.length ? `<div class="card" style="margin-bottom:16px;border-color:var(--brand-200)"><b>Có kết quả mới</b> cho ${newResults.length} yêu cầu sửa thông tin của bạn, xem ở bảng "Yêu cầu sửa đã gửi" bên dưới.</div>` : "";
    main.innerHTML = `${notice}
      <div class="card">
        <div class="toolbar" style="margin:0"><h3 style="margin:0">Hồ sơ của tôi</h3>
          ${p ? '<button class="primary" id="update-profile">Cập nhật thông tin</button>' : ""}</div>
        ${p ? `<p class="muted">Đây là thông tin nhân sự công ty đang lưu về bạn. Chỉ bạn và quản trị viên xem được; trợ lý AI chỉ hiển thị cho bạn khi bạn hỏi
          "thông tin của tôi". Nếu thiếu hoặc sai chỗ nào, bấm <b>Cập nhật thông tin</b>: quản trị viên sẽ xem và duyệt rồi mới cập nhật.</p>
          <table>${rows.map(([label, f, v]) => {
            const val = v ?? (f ? p[f] : p.employee_code);
            return `<tr><td class="muted" style="width:200px">${esc(label)}</td><td><b>${val ? esc(fmtVal(f, val)) : '<span class="muted">chưa có dữ liệu</span>'}</b></td></tr>`;
          }).join("")}${p.roles.length ? `<tr><td class="muted">Chức vụ trên sơ đồ</td><td><b>${p.roles.map((r) => esc(`${r.title} – ${r.unit_name}`)).join("; ")}</b></td></tr>` : ""}</table>`
        : `<div class="empty">Tài khoản của bạn chưa được liên kết với hồ sơ nhân sự, nên trợ lý AI chưa thể trả lời "thông tin của tôi".
          ${lr ? `<p>Bạn đã xin liên kết với hồ sơ <b>${esc(lr.employee_name)}</b>${lr.job_title ? ` (${esc(lr.job_title)})` : ""} —
            ${lr.status === "pending" ? "đang chờ quản trị viên duyệt." : `bị từ chối${lr.admin_note ? `: ${esc(lr.admin_note)}` : "."}`}</p>` : "<p>Hãy chọn hồ sơ của bạn trong danh sách nhân sự, quản trị viên sẽ duyệt.</p>"}
          ${lr?.status === "pending" ? `<button class="ghost" id="link-withdraw">Rút lại</button> ` : ""}
          <button class="primary" id="link-ask">${lr?.status === "pending" ? "Chọn lại hồ sơ" : "Chọn hồ sơ của tôi"}</button></div>`}
      </div>
      ${data.requests.length ? `<div class="card" style="margin-top:16px"><h3>Yêu cầu sửa đã gửi</h3>
        <table><tr><th>Thông tin</th><th>Từ</th><th>Thành</th><th>Trạng thái</th><th>Gửi lúc</th><th></th></tr>
          ${data.requests.map((r) => `<tr><td>${esc(data.fields[r.field] || r.field)}</td><td class="muted">${esc(fmtVal(r.field, r.old_value) || "—")}</td>
            <td><b>${esc(fmtVal(r.field, r.new_value))}</b></td>
            <td><span class="badge ${RSTATUS[r.status][1]}">${RSTATUS[r.status][0]}</span>${r.admin_note ? `<div class="muted small">${esc(r.admin_note)}</div>` : ""}</td>
            <td class="muted">${esc((r.created_at || "").slice(0, 16))}</td>
            <td>${r.status === "pending" ? `<button class="link danger" data-withdraw="${r.id}">Rút lại</button>` : ""}</td></tr>`).join("")}
        </table></div>` : ""}`;
    if (state.user.profile_notices) {  // mở trang = đã xem kết quả
      api("/api/me/profile/seen", { method: "POST" }).then(refreshPending).catch(() => {});
    }
    $("#link-ask")?.addEventListener("click", async () => {
      try {
        const free = await api("/api/me/link-options");
        openForm("Chọn hồ sơ nhân sự của tôi", [
          { type: "info", label: "Chọn đúng họ tên của bạn. Quản trị viên sẽ kiểm tra và duyệt rồi tài khoản mới được liên kết." },
          { name: "employee_id", label: "Nhân viên", type: "select", numeric: true, required: true, search: true,
            options: [["", "— Chọn —"], ...free.map((e) => [e.id, `${e.full_name}${e.job_title ? " – " + e.job_title : ""}${e.unit_name ? " (" + e.unit_name + ")" : ""}`])] },
        ], {}, (d) => {
          if (!d.employee_id) throw new Error("Hãy chọn một nhân viên");
          return api("/api/me/link-request", { method: "POST", body: { employee_id: d.employee_id } }).then(() => toast("Đã gửi, chờ quản trị viên duyệt."));
        }, "Gửi yêu cầu");
      } catch (e) { toast(e.message, "err"); }
    });
    $("#link-withdraw")?.addEventListener("click", async () => {
      try { await api(`/api/me/link-request/${lr.id}`, { method: "DELETE" }); toast("Đã rút lại."); render(); } catch (e) { toast(e.message, "err"); }
    });
    $("#update-profile")?.addEventListener("click", () => openForm("Cập nhật thông tin của tôi", [
      { type: "info", label: "Sửa vào ô cần đổi hoặc điền chỗ còn thiếu; ô không đổi sẽ được bỏ qua. Số điện thoại, email, ngày sinh được cập nhật ngay; các thông tin còn lại cần quản trị viên duyệt. Ngày nhập dạng 30/03/2011." },
      ...Object.entries(data.fields).map(([f, label]) => ({ name: f, label, placeholder: "chưa có dữ liệu" })),
      { name: "reason", label: "Ghi chú cho quản trị viên (không bắt buộc)" },
    ], Object.fromEntries(Object.keys(data.fields).map((f) => [f, fmtVal(f, p[f])])), async (d) => {
      const { reason, ...values } = d;
      const r = await api("/api/me/profile/update", { method: "POST", body: { values, reason } });
      const L = data.fields, names = (a) => a.map((f) => L[f]).join(", ");
      toast([r.applied.length ? `Đã cập nhật: ${names(r.applied)}.` : "", r.pending.length ? `Chờ quản trị viên duyệt: ${names(r.pending)}.` : ""].filter(Boolean).join(" "));
    }, "Gửi cập nhật"));
    main.querySelectorAll("[data-withdraw]").forEach((b) => (b.onclick = async () => {
      try { await api(`/api/me/change-requests/${b.dataset.withdraw}`, { method: "DELETE" }); toast("Đã rút lại."); render(); } catch (e) { toast(e.message, "err"); }
    }));
  },

  async memory(main) {
    let m = await api("/api/memory");
    const draw = () => {
      const active = m.notes.filter((n) => n.active), pending = m.notes.filter((n) => !n.active);
      const noteRow = (n) => `<tr><td><span data-note="${n.id}">${esc(n.text)}</span>
          <div class="muted small">${n.active ? (n.source === "user" ? "Bạn tự viết/sửa" : "AI ghi từ cuộc chat") : "Chờ xác nhận: AI mới suy ra một lần, chỉ dùng khi bạn hỏi lại tương tự ở cuộc chat khác"} · ${esc((n.updated_at || "").slice(0, 16))}</div></td>
        <td style="white-space:nowrap"><button class="link" data-mem-edit="${n.id}">Sửa</button>${n.active ? "" : ` · <button class="link" data-mem-ok="${n.id}">Xác nhận</button>`} · <button class="link danger" data-mem-del="${n.id}">Xoá</button></td></tr>`;
      main.innerHTML = `
        <div class="card">
          <div class="toolbar" style="margin:0"><h3 style="margin:0">AI nhớ gì về tôi</h3>
            <button class="${m.enabled ? "ghost" : "primary"}" id="mem-toggle">${m.enabled ? "Tắt bộ nhớ" : "Bật bộ nhớ cá nhân"}</button></div>
          <p class="muted">Khi bật, trợ lý ghi lại vài ghi chú ngắn về công việc và cách bạn muốn được trả lời (sau khi một cuộc chat dừng khoảng ${m.idle_minutes} phút)
            và dùng chúng ở các lần hỏi sau, nên càng dùng càng hiểu bạn hơn. Ghi chú chỉ dành cho tài khoản của bạn.
            Trợ lý <b>không</b> ghi lương/thu nhập, sức khoẻ, giấy tờ, mật khẩu, số điện thoại/email hay nội dung tài liệu công ty.
            Bạn xem, sửa, xoá từng ghi chú hoặc xoá hết bất cứ lúc nào. Tắt bộ nhớ là trợ lý ngừng ghi và ngừng dùng các ghi chú này.</p>
          <p class="muted small">Chỉ các cuộc chat từ lúc bạn bật mới được xem xét. Quản trị viên có thể xem để quản lý hệ thống.</p>
        </div>
        ${m.enabled ? `<div class="card" style="margin-top:16px">
          <div class="toolbar" style="margin:0"><h3 style="margin:0">Ghi chú đang dùng (${active.length}/${m.max_notes})</h3>
            <span class="btn-group"><button class="ghost" id="mem-refresh">Cập nhật từ các cuộc chat gần đây</button>
              ${m.notes.length ? '<button class="ghost danger" id="mem-clear">Xoá toàn bộ</button>' : ""}</span></div>
          ${active.length ? `<table>${active.map(noteRow).join("")}</table>` : '<div class="empty">Chưa có ghi chú nào. Hãy chat với trợ lý, hoặc tự viết một ghi chú bên dưới.</div>'}
          <form id="mem-add" class="toolbar" style="margin-top:12px"><input name="text" maxlength="160" placeholder="Tự viết một ghi chú cho trợ lý, VD: Tôi phụ trách mảng đấu thầu miền Nam" style="flex:1"><button class="primary">Thêm</button></form>
        </div>
        ${pending.length ? `<div class="card" style="margin-top:16px"><h3>Đang theo dõi (chưa dùng)</h3><table>${pending.map(noteRow).join("")}</table></div>` : ""}` : ""}`;
      $("#mem-toggle").onclick = async () => {
        if (m.enabled && !(await confirmBox("Tắt bộ nhớ cá nhân?", "Trợ lý sẽ ngừng ghi và ngừng dùng các ghi chú. Ghi chú hiện có vẫn được giữ, bạn có thể xoá bất cứ lúc nào.", { okText: "Tắt" }))) return;
        try { m = await api("/api/memory/enabled", { method: "PUT", body: { enabled: !m.enabled } }); draw(); toast(m.enabled ? "Đã bật bộ nhớ cá nhân." : "Đã tắt bộ nhớ cá nhân."); } catch (e) { toast(e.message, "err"); }
      };
      if (!m.enabled) return;
      const act = async (fn) => { try { m = await fn(); draw(); } catch (e) { toast(e.message, "err"); } };
      $("#mem-add").onsubmit = (e) => {
        e.preventDefault();
        const text = e.target.elements.text.value.trim();
        if (text) act(() => api("/api/memory", { method: "POST", body: { text } }));
      };
      $("#mem-refresh").onclick = async (e) => {
        e.target.disabled = true;
        e.target.textContent = "Đang đọc các cuộc chat...";
        try {
          const r = await api("/api/memory/refresh", { method: "POST" });
          m = r;
          toast(r.processed ? "Đã cập nhật ghi chú." : "Chưa có cuộc chat mới để xem xét (hoặc AI đang bận, thử lại sau).");
        } catch (err) { toast(err.message, "err"); }
        draw();
      };
      if ($("#mem-clear")) $("#mem-clear").onclick = async () => {
        if (await confirmBox("Xoá toàn bộ ghi chú?", "Trợ lý sẽ quên mọi điều đã ghi về bạn. Không thể khôi phục.", { okText: "Xoá hết", danger: true })) act(() => api("/api/memory", { method: "DELETE" }));
      };
      main.querySelectorAll("[data-mem-del]").forEach((b) => (b.onclick = () => act(() => api(`/api/memory/${b.dataset.memDel}`, { method: "DELETE" }))));
      main.querySelectorAll("[data-mem-ok]").forEach((b) => (b.onclick = () => {
        const n = m.notes.find((x) => x.id == b.dataset.memOk);
        act(() => api(`/api/memory/${n.id}`, { method: "PUT", body: { text: n.text } }));
      }));
      main.querySelectorAll("[data-mem-edit]").forEach((b) => (b.onclick = async () => {
        const n = m.notes.find((x) => x.id == b.dataset.memEdit);
        const text = await ask({ title: "Sửa ghi chú", input: n.text, okText: "Lưu" });
        if (text && text.trim() && text.trim() !== n.text) act(() => api(`/api/memory/${n.id}`, { method: "PUT", body: { text: text.trim() } }));
      }));
    };
    draw();
  },

  async access(main) {
    const isAdmin = state.user.role === "admin";
    state.accessFilter ??= { tab: "pending", q: "", month: "" };
    const f0 = state.accessFilter;
    const reqs = await api(isAdmin ? `/api/access-requests?tab=${f0.tab}&q=${encodeURIComponent(f0.q)}&month=${f0.month}` : "/api/access-requests");
    if (!isAdmin && state.user.pending_requests) {  // user mở trang = đã xem kết quả
      await api("/api/access-requests/seen", { method: "POST" });
      await refreshPending();
    }
    const feats = (r) => [...r.features.map((f) => esc(FEATURE_LABELS[f])),
      ...(r.extra_mb ? [`Thêm ${r.extra_mb} MB dung lượng${r.granted_mb ? ` (đã cấp ${r.granted_mb} MB)` : ""}`] : [])].join(", ");
    const STATUS = { pending: ["Chờ duyệt", "warn"], approved: ["Đã duyệt", "ok"], rejected: ["Từ chối", "warn"], cancelled: ["Đã rút lại", ""] };
    const status = (r) => `<span class="badge ${STATUS[r.status][1]}">${STATUS[r.status][0]}</span>`;
    if (isAdmin) {
      const f = state.accessFilter;
      main.innerHTML = `
        <div class="toolbar"><h2 style="margin:0">Yêu cầu quyền truy cập</h2>
          <div class="btn-group"><button class="${f.tab === "pending" ? "primary" : "ghost"}" data-tab="pending">Chờ duyệt${state.user.pending_requests ? ` (${state.user.pending_requests})` : ""}</button>
            <button class="${f.tab === "history" ? "primary" : "ghost"}" data-tab="history">Lịch sử</button></div></div>
        ${f.tab === "history" ? `<div class="toolbar"><input id="acc-q" placeholder="Lọc theo tên / tên đăng nhập..." value="${esc(f.q)}" style="max-width:300px">
          <input id="acc-month" type="month" value="${esc(f.month)}" style="max-width:180px"></div>` : ""}
        <div class="card">${reqs.length ? `<table>
          <tr><th>Gửi lúc</th><th>Người xin</th><th>Quyền xin</th><th>Lý do</th><th>Trạng thái</th><th></th></tr>
          ${reqs.map((r) => `<tr><td class="muted">${esc(r.created_at)}</td><td><b>${esc(r.full_name || r.username)}</b><div class="muted small">${esc(r.username)}</div></td>
            <td>${feats(r)}</td><td>${esc(r.reason || "—")}${r.admin_note ? `<div class="muted small">Ghi chú admin: ${esc(r.admin_note)}</div>` : ""}</td>
            <td>${status(r)}${r.decided_at ? `<div class="muted small">${esc(r.decided_at)}</div>` : ""}${r.updated_at && r.status === "pending" ? `<div class="muted small">Đã chỉnh sửa ${esc(r.updated_at)}</div>` : ""}</td>
            <td>${r.status === "pending" ? `<button class="link" data-ok="${r.id}">Duyệt</button> · <button class="link" data-no="${r.id}">Từ chối</button>` : ""}</td></tr>`).join("")}
        </table>` : `<div class="empty">${f.tab === "pending" ? "Không có yêu cầu nào chờ duyệt." : "Không có yêu cầu phù hợp."}</div>`}</div>`;
      main.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { f.tab = b.dataset.tab; render(); }));
      if (f.tab === "history") {
        let t;
        $("#acc-q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { f.q = e.target.value; render(); }, 300); };
        $("#acc-month").onchange = (e) => { f.month = e.target.value; render(); };
      }
      const decide = async (id, approve) => {
        const send = async (note) => {
          await api(`/api/access-requests/${id}/decide`, { method: "POST", body: { approve, note } });
          await refreshPending();
          toast(approve ? "Đã duyệt và cấp quyền cho người xin." : "Đã từ chối yêu cầu.");
        };
        const r = reqs.find((x) => x.id == id);
        if (approve && r.extra_mb) {  // đơn xin thêm dung lượng: cho admin chỉnh số MB trước khi duyệt
          return openForm(`Duyệt yêu cầu của ${r.full_name || r.username}`, [
            { name: "grant_mb", label: `Số MB cấp thêm (người xin yêu cầu ${r.extra_mb} MB)`, type: "number", required: true },
          ], { grant_mb: r.extra_mb }, async (d) => {
            await api(`/api/access-requests/${id}/decide`, { method: "POST", body: { approve: true, note: "", grant_mb: d.grant_mb } });
            await refreshPending();
            toast("Đã duyệt và cấp quyền/dung lượng cho người xin.");
          }, "Duyệt");
        }
        if (approve) return send("").then(() => render()).catch((e) => toast(e.message, "err"));
        openForm(`Từ chối yêu cầu của ${r.full_name || r.username}`, [
          { name: "note", label: "Lý do từ chối (người xin sẽ thấy nội dung này)", type: "textarea", required: true, placeholder: "VD: Quyền này chưa phù hợp với vị trí công việc..." },
        ], {}, (d) => {
          if (!d.note.trim()) throw new Error("Vui lòng nhập lý do từ chối");
          return send(d.note.trim());
        }, "Từ chối");
      };
      main.querySelectorAll("[data-ok]").forEach((b) => (b.onclick = () => decide(b.dataset.ok, true)));
      main.querySelectorAll("[data-no]").forEach((b) => (b.onclick = () => decide(b.dataset.no, false)));
      return;
    }
    const pending = reqs.some((r) => r.status === "pending");
    const available = Object.entries(FEATURE_LABELS).filter(([f]) => !can(f));
    main.innerHTML = `
      <div class="toolbar"><h2 style="margin:0">Quyền truy cập</h2>
        ${!pending ? '<button class="primary" id="ask-access">+ Xin cấp quyền</button>' : ""}</div>
      <div class="card"><h3>Quyền hiện có</h3>
        <p>${state.user.permissions.length ? state.user.permissions.map((f) => `<span class="badge ok">${esc(FEATURE_LABELS[f])}</span>`).join(" ") : '<span class="muted">Chưa được cấp quyền thêm nào.</span>'}</p>
        ${pending ? '<p class="muted">Bạn đang có yêu cầu chờ duyệt; quản trị viên đã được thông báo.</p>' : ""}
        ${!available.length ? '<p class="muted">Bạn đã có tất cả các quyền có thể xin. Bạn vẫn có thể xin thêm dung lượng lưu trữ.</p>' : ""}</div>
      <div class="card" style="margin-top:16px"><h3>Yêu cầu đã gửi <span class="muted small">(đơn đã xử lý hiện trong 30 ngày)</span></h3>${reqs.length ? `<table>
        <tr><th>Thời gian</th><th>Quyền xin</th><th>Lý do</th><th>Trạng thái</th><th></th></tr>
        ${reqs.map((r) => `<tr><td class="muted">${esc(r.created_at)}</td><td>${feats(r)}</td>
          <td>${esc(r.reason || "—")}${r.admin_note ? `<div class="muted small">Phản hồi: ${esc(r.admin_note)}</div>` : ""}</td>
          <td>${status(r)}${r.updated_at && r.status === "pending" ? `<div class="muted small">Đã chỉnh sửa ${esc(r.updated_at)}</div>` : ""}</td>
          <td>${r.status === "pending" ? `<button class="link" data-edit-req="${r.id}">Chỉnh sửa</button> · <button class="link" data-withdraw="${r.id}">Rút lại</button>` : ""}</td></tr>`).join("")}
      </table>` : '<div class="empty">Bạn chưa gửi yêu cầu nào.</div>'}</div>`;
    // Gửi mới hoặc chỉnh sửa đơn đang chờ duyệt (sửa lỗi nhập, hoặc xin thêm quyền)
    const requestForm = (req) => openForm(req ? "Chỉnh sửa yêu cầu quyền" : "Xin cấp quyền truy cập", [
      ...available.map(([f, l]) => ({ name: f, label: l, type: "check", default: req?.features.includes(f) })),
      { name: "extra_mb", label: "Xin thêm dung lượng lưu trữ file riêng (MB, bỏ trống nếu không cần) — gợi ý: 100, 500, 1000", type: "number", placeholder: "VD: 500" },
      { name: "reason", label: "Lý do / mục đích sử dụng", type: "textarea", required: true, placeholder: "VD: cần xem quy trình để phục vụ công việc phòng..." },
    ], { reason: req?.reason, extra_mb: req?.extra_mb }, async (d) => {
      const features = available.map(([f]) => f).filter((f) => d[f]);
      const extra_mb = d.extra_mb ? Math.round(d.extra_mb) : null;
      if (!features.length && !extra_mb) throw new Error("Hãy chọn ít nhất một quyền hoặc nhập dung lượng cần xin thêm");
      if (extra_mb != null && extra_mb < 1) throw new Error("Dung lượng xin thêm phải lớn hơn 0 MB");
      const body = { features, extra_mb, reason: d.reason.trim() };
      if (req) await api(`/api/access-requests/${req.id}`, { method: "PUT", body });
      else await api("/api/access-requests", { method: "POST", body });
      toast(req ? "Đã cập nhật yêu cầu. Quản trị viên sẽ thấy nội dung mới." : "Đã gửi yêu cầu. Quản trị viên sẽ nhận được thông báo để duyệt.");
    }, req ? "Lưu thay đổi" : "Gửi yêu cầu");
    const ask = $("#ask-access");
    if (ask) ask.onclick = () => requestForm();
    main.querySelectorAll("[data-edit-req]").forEach((b) => (b.onclick = () => requestForm(reqs.find((r) => r.id == b.dataset.editReq))));
    main.querySelectorAll("[data-withdraw]").forEach((b) => (b.onclick = () => openForm("Rút lại yêu cầu", [
      { name: "_", label: "Yêu cầu sẽ bị huỷ và quản trị viên không còn thấy ở danh sách chờ duyệt. Bạn có thể gửi yêu cầu mới sau đó.", type: "info" },
    ], {}, async () => {
      await api(`/api/access-requests/${b.dataset.withdraw}`, { method: "DELETE" });
      toast("Đã rút lại yêu cầu.");
    }, "Rút lại yêu cầu")));
  },

  async chat(main) {
    const [ai, convs] = await Promise.all([api("/api/ai/status"), api("/api/conversations")]);
    state.convs = convs;
    if (state.chatId && !convs.some((c) => c.id === state.chatId)) state.chatId = null;
    const canAttach = !!state.user.can_use_ai;  // file đính kèm lưu ở kho riêng của từng tài khoản (không vào thư viện chung)
    const attachMeta = canAttach ? await api("/api/my-files/meta").catch(() => null) : null;
    main.innerHTML = `
      <div class="cg ${state.chatSidebar === false ? "side-closed" : ""}" id="cg">
        <aside class="cg-side">
          <div class="cg-side-head">
            <button class="cg-new" id="new-chat" title="Đoạn chat mới"><span class="plus">+</span> Đoạn chat mới</button>
            <button class="cg-icon" id="hide-side" title="Ẩn lịch sử">«</button>
          </div>
          <input class="cg-filter" id="conv-filter" placeholder="Tìm trong lịch sử...">
          <nav class="cg-list" id="conv-list"></nav>
        </aside>
        <section class="cg-main">
          <div class="cg-top">
            <button class="cg-icon" id="show-side" title="Hiện lịch sử">☰</button>
            <button class="cg-icon" id="new-chat-2" title="Đoạn chat mới">+</button>
            <div class="cg-title" id="cg-title"></div>
            ${ai.configured ? "" : `<span class="badge warn">Chưa cấu hình ${esc(ai.key_name || "API key")}</span>`}
          </div>
          <div class="cg-log" id="log"></div>
          <div class="cg-composer">
            <form class="cg-box" id="chat-form">
              <div class="cg-files" id="cg-files"></div>
              ${canAttach ? `<button class="cg-attach" id="attach" type="button" title="Đính kèm tài liệu, ảnh, file ghi âm (hoặc Ctrl+V để dán ảnh)">${icon("upload")}</button>
              <input type="file" id="attach-file" hidden multiple>` : ""}
              <textarea id="q" rows="1" placeholder="Hỏi trợ lý điều hành AZB..."></textarea>
              <button class="cg-send" id="send" type="submit" title="Gửi (Enter)">↑</button>
            </form>
            <div class="cg-quota" id="cg-quota"></div>
            <div class="cg-hint">Enter để gửi · Shift+Enter xuống dòng · AI có thể sai, hãy kiểm tra lại số liệu quan trọng</div>
          </div>
        </section>
      </div>`;

    const log = $("#log"), q = $("#q");
    const jobOf = (convId) => [...state.jobs.values()].find((j) => j.convId === convId);
    const currentJob = () => (state.chatJob ? state.jobs.get(state.chatJob) : state.chatId != null ? jobOf(state.chatId) : null);
    const setBusy = () => { const b = $("#send"); if (b) b.disabled = !!currentJob(); };
    const renderList = () => {
      const f = norm($("#conv-filter").value.trim());
      const list = state.convs.filter((c) => !f || norm(c.title).includes(f));
      const groups = {};
      list.forEach((c) => (groups[convGroup(c.updated_at)] ??= []).push(c));
      const fresh = [...state.jobs.values()].filter((j) => j.convId == null && (!f || norm(j.text).includes(f)));
      const freshHtml = fresh.length ? `<div class="cg-group">Đang trả lời</div>${fresh.map((j) => `
        <div class="cg-item busy ${j.token === state.chatJob ? "active" : ""}" data-job="${j.token}" title="${esc(j.text)}">
          <span class="t">${esc(j.text)}</span><span class="dots mini"><i></i><i></i><i></i></span>
        </div>`).join("")}` : "";
      $("#conv-list").innerHTML = list.length || fresh.length
        ? freshHtml + Object.entries(groups).map(([g, items]) => `
            <div class="cg-group">${esc(g)}</div>
            ${items.map((c) => `
              <div class="cg-item ${c.id === state.chatId && !state.chatJob ? "active" : ""} ${jobOf(c.id) ? "busy" : ""}" data-id="${c.id}" title="${esc(c.title)}">
                <span class="t">${esc(c.title)}</span>
                ${jobOf(c.id) ? '<span class="dots mini"><i></i><i></i><i></i></span>' : state.unseen.has(c.id) ? '<span class="unseen" title="Đã có câu trả lời mới"></span>' : ""}
                <span class="acts"><button data-rename="${c.id}" title="Đổi tên">✎</button><button data-remove="${c.id}" title="Xoá">✕</button></span>
              </div>`).join("")}`).join("")
        : `<div class="cg-empty">${f ? "Không tìm thấy đoạn chat." : "Chưa có lịch sử. Câu hỏi đầu tiên sẽ tạo đoạn chat mới."}</div>`;
      $("#cg-title").textContent = state.chatJob ? "Đoạn chat mới" : state.convs.find((c) => c.id === state.chatId)?.title || "Đoạn chat mới";
    };
    const refreshList = async () => {
      state.convs = await api("/api/conversations");
      if ($("#conv-list")) renderList();
    };

    const welcome = () => {
      const name = state.user.full_name || state.user.username;
      log.innerHTML = `
        <div class="cg-welcome">
          <div class="cg-logo">AZB</div>
          <h2>Xin chào ${esc(name)}, hôm nay cần nắm thông tin gì?</h2>
          <p class="muted">Hỏi về tổ chức, nhân sự, quy trình, tài liệu, mục tiêu. Trợ lý tra cứu trực tiếp dữ liệu công ty.</p>
          <div class="cg-suggest">${CHAT_SUGGESTIONS.map((s) => `<button>${esc(s)}</button>`).join("")}</div>
        </div>`;
      log.querySelectorAll(".cg-suggest button").forEach((b) => (b.onclick = () => send(b.textContent)));
    };
    const scroll = () => (log.scrollTop = log.scrollHeight);
    const pendingHtml = (job) => msgHtml({ role: "user", content: job.text }) + `<div class="msg assistant pending" id="pending"><div class="av">AZB</div>
        <div class="body"><span class="dots"><i></i><i></i><i></i></span> Đang tra cứu dữ liệu và phân tích...</div></div>`;
    // open(id): xem đoạn chat đã lưu; open(null, token): xem đoạn chat mới đang chờ trả lời; open(null): đoạn chat trống
    const open = async (id, token = null) => {
      state.chatId = id;
      state.chatJob = token;
      if (id != null) state.unseen.delete(id);
      renderList();
      setBusy();
      if (token) {
        const job = state.jobs.get(token);
        log.innerHTML = `<div class="cg-thread">${job ? pendingHtml(job) : ""}</div>`;
        scroll();
        q.focus();
        return;
      }
      if (!id) {
        welcome();
        q.focus();
        return;
      }
      log.innerHTML = `<div class="cg-thread"><div class="muted">Đang tải...</div></div>`;
      let conv, job;
      for (let i = 0; i < 2; i++) {
        job = jobOf(id);
        conv = await api(`/api/conversations/${id}`);
        if (state.chatId !== id || state.chatJob) return;
        if (!job || state.jobs.has(job.token)) break; // job xong giữa lúc tải → tải lại để có câu trả lời
      }
      job = jobOf(id);
      log.innerHTML = `<div class="cg-thread">${conv.messages.map(msgHtml).join("")}${job ? pendingHtml(job) : ""}</div>`;
      setBusy();
      scroll();
      q.focus();
    };

    // Tài liệu đính kèm: lưu ở kho riêng của tài khoản này; file có sẵn chữ đọc ngay, ảnh/scan/ghi âm chỉ đọc bằng AI lúc gửi câu hỏi
    const attached = [];  // {id, name, status, deferred}
    const drawQuota = () => {
      const u = attachMeta?.usage, el = $("#cg-quota");
      if (!u || !el) return;
      el.className = "cg-quota" + (u.percent >= 90 ? " warn" : "");
      el.textContent = u.quota_mb == null ? `Dữ liệu riêng: đã dùng ${u.used_mb} MB (không giới hạn)`
        : `Dữ liệu riêng: còn ${u.remaining_mb} / ${u.quota_mb} MB`;
    };
    const refreshQuota = async () => { try { attachMeta.usage = (await api("/api/my-files/meta")).usage; } catch {} drawQuota(); };
    drawQuota();
    const renderFiles = () => {
      $("#cg-files").innerHTML = attached.map((a, i) => a.preview ? `<span class="cg-thumb ${a.status}" title="${esc(a.name)}">
        <img src="${a.preview}" alt="">
        ${a.status === "ok" && !a.deferred ? "" : `<span class="s">${a.status === "failed" ? "lỗi" : a.deferred ? "đọc khi gửi" : "đang tải..."}</span>`}
        <button type="button" data-rm="${i}" title="Bỏ đính kèm">✕</button></span>` : `<span class="cg-file ${a.status}">
        <span class="n" title="${esc(a.name)}">${esc(a.name)}</span>
        <span class="s">${a.status === "ok" ? (a.deferred ? "✓ sẽ đọc khi gửi" : "✓ đã đọc") : a.status === "failed" ? "lỗi" : "đang tải..."}</span>
        <button type="button" data-rm="${i}" title="Bỏ đính kèm">✕</button></span>`).join("");
      $("#cg-files").querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { attached.splice(Number(b.dataset.rm), 1); renderFiles(); }));
    };
    const watchAttachment = async (a) => {
      for (let i = 0; i < 200 && attached.includes(a); i++) {  // tối đa ~10 phút (ghi âm dài)
        await new Promise((r) => setTimeout(r, 3000));
        try {
          const d = await api(`/api/my-files/${a.id}`);
          if (d.extract_status === "ok" || d.extract_status === "failed" || d.extract_status === "needs_ocr") {
            a.deferred = d.extract_status === "needs_ocr";  // ảnh/scan/ghi âm: AI đọc lúc gửi câu hỏi (tiết kiệm hạn mức)
            a.status = d.extract_status === "failed" ? "failed" : "ok";
            if (a.status === "failed") toast(d.extract_note || "Không đọc được file này.", "err");
            break;
          }
        } catch { break; }
      }
      if ($("#cg-files")) renderFiles();
    };
    if (canAttach && $("#attach")) {
      const addFiles = async (files) => {
        for (const f of files) {
          const ext = "." + f.name.split(".").pop().toLowerCase();
          if (attachMeta && !attachMeta.allowed_ext.includes(ext)) { toast(`Chưa hỗ trợ định dạng ${ext}. Hỗ trợ: ${attachMeta.allowed_ext.join(", ")}`, "err"); continue; }
          if (attachMeta && f.size > attachMeta.max_mb * 1048576) { toast(`${f.name} vượt quá ${attachMeta.max_mb} MB.`, "err"); continue; }
          const left = attachMeta?.usage?.remaining_mb;
          if (left != null && f.size > left * 1048576) { toast(`Không đủ dung lượng riêng (còn ${left} MB). Xoá bớt file cũ ở "Dữ liệu của tôi" hoặc nhờ admin nâng hạn mức.`, "err"); continue; }
          const a = { id: null, name: f.name, status: "uploading", preview: f.type.startsWith("image/") ? URL.createObjectURL(f) : "" };
          attached.push(a);
          renderFiles();
          try {
            const fd = new FormData();
            fd.append("file", f);
            a.id = (await api("/api/my-files", { method: "POST", body: fd })).id;
            a.status = "processing";
            renderFiles();
            refreshQuota();
            watchAttachment(a);
          } catch (err) {
            attached.splice(attached.indexOf(a), 1);
            renderFiles();
            toast(err.message, "err");
          }
        }
      };
      $("#attach").onclick = () => $("#attach-file").click();
      $("#attach-file").onchange = (e) => {
        const files = [...e.target.files];
        e.target.value = "";
        addFiles(files);
      };
      // Ctrl+V dán ảnh (ảnh chụp màn hình, ảnh copy từ web/Zalo...) → đính kèm như file; dán chữ thường vẫn bình thường
      q.addEventListener("paste", (e) => {
        const imgs = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith("image/"));
        if (!imgs.length) return;
        e.preventDefault();
        const stamp = new Date().toTimeString().slice(0, 8).replace(/:/g, "");
        addFiles(imgs.map((f, i) => {
          const ext = { "image/jpeg": "jpg", "image/webp": "webp" }[f.type] || "png";
          return new File([f], `anh-dan-${stamp}${imgs.length > 1 ? "-" + (i + 1) : ""}.${ext}`, { type: f.type });
        }));
      });
    }

    const send = async (text) => {
      text = text.trim();
      if (attached.some((a) => a.status === "uploading" || a.status === "processing")) return toast("Đợi trợ lý đọc xong file đính kèm rồi hãy gửi.");
      const ready = attached.filter((a) => a.status === "ok");
      if (ready.length) {
        const list = ready.map((a) => `"${a.name}" (id tài liệu ${a.id})`).join(", ");
        text = `[Đính kèm: ${list}]\n${text || "Hãy đọc và tóm tắt nội dung tài liệu đính kèm."}`;
        attached.length = 0;
        renderFiles();
      }
      if (!text || currentJob()) return;
      const job = { token: ++state.jobSeq, convId: state.chatId, text };
      state.jobs.set(job.token, job);
      if (job.convId == null) state.chatJob = job.token;
      if (!log.querySelector(".cg-thread")) log.innerHTML = `<div class="cg-thread"></div>`;
      log.querySelector(".cg-thread").insertAdjacentHTML("beforeend", pendingHtml(job));
      q.value = "";
      autosize();
      scroll();
      renderList();
      setBusy();
      let res;
      try {
        res = await api("/api/chat", { method: "POST", body: { content: text, conversation_id: job.convId }, signal: AbortSignal.timeout(120000) });
      } catch (err) {
        const reason = err.name === "TimeoutError" ? "AI trả lời quá lâu, hãy thử lại sau ít phút." : err.message || "Không nhận được phản hồi từ máy chủ, hãy thử lại.";
        res = { answer: "Lỗi: " + reason, error: "client" };
      }
      finishJob(job, res);
    };
    state.chatUI = { refreshList, setBusy, open, scroll, q };

    const autosize = () => {
      q.style.height = "auto";
      q.style.height = Math.min(q.scrollHeight, 220) + "px";
    };
    q.oninput = autosize;
    q.onkeydown = (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        send(q.value);
      }
    };
    $("#chat-form").onsubmit = (e) => {
      e.preventDefault();
      send(q.value);
    };
    $("#new-chat").onclick = $("#new-chat-2").onclick = () => open(null);
    $("#conv-filter").oninput = renderList;
    const toggleSide = (show) => {
      state.chatSidebar = show;
      $("#cg").classList.toggle("side-closed", !show);
    };
    $("#hide-side").onclick = () => toggleSide(false);
    $("#show-side").onclick = () => toggleSide(true);
    $("#conv-list").onclick = async (e) => {
      const ren = e.target.closest("[data-rename]"), rem = e.target.closest("[data-remove]");
      if (ren) {
        const c = state.convs.find((x) => x.id == ren.dataset.rename);
        const title = await ask({ title: "Đổi tên đoạn chat", input: c.title, okText: "Lưu" });
        if (title?.trim()) {
          await api(`/api/conversations/${c.id}`, { method: "PUT", body: { title } });
          await refreshList();
        }
        return;
      }
      if (rem) {
        const id = Number(rem.dataset.remove);
        if (jobOf(id)) return toast("Trợ lý đang trả lời đoạn chat này, hãy đợi xong rồi xoá.");
        let att = { files: [], kept: 0 };
        try { att = await api(`/api/conversations/${id}/files`); } catch {}
        let withFiles = false;
        if (att.files.length) {
          const size = att.files.reduce((a, f) => a + (f.size_bytes || 0), 0);
          const choice = await askChoice({
            title: "Xoá đoạn chat này?",
            message: `Đoạn chat có ${att.files.length} file đính kèm (${fmtSize(size) || "0 KB"}) chỉ dùng trong đoạn chat này. Xoá luôn file để giải phóng dung lượng?${att.kept ? ` (${att.kept} file khác còn được đoạn chat khác dùng nên sẽ được giữ lại.)` : ""} Không thể khôi phục.`,
            options: [{ label: "Xoá chat và file", value: "all", danger: true }, { label: "Chỉ xoá chat, giữ file", value: "chat", primary: true }, { label: "Huỷ", value: null }],
          });
          if (!choice) return;
          withFiles = choice === "all";
        } else if (!(await ask({ title: "Xoá đoạn chat này?", message: "Không thể khôi phục.", okText: "Xoá", danger: true }))) return;
        await api(`/api/conversations/${id}${withFiles ? "?delete_files=true" : ""}`, { method: "DELETE" });
        if (withFiles) toast("Đã xoá đoạn chat và file đính kèm.");
        if (state.chatId === id && !state.chatJob) await open(null);
        await refreshList();
        return;
      }
      const item = e.target.closest(".cg-item");
      if (!item) return;
      if (item.dataset.job) open(null, Number(item.dataset.job));
      else open(Number(item.dataset.id));
    };
    await open(state.chatId);
  },
};

// Câu trả lời về tới dù người dùng đang xem đoạn chat khác hay trang khác: chỉ cập nhật màn hình nếu đúng đoạn đang xem
async function finishJob(job, res) {
  const viewing = state.chatJob === job.token || (job.convId != null && state.chatId === job.convId && !state.chatJob);
  state.jobs.delete(job.token);
  const ok = !res.error;
  if (ok && job.convId == null) {
    job.convId = res.conversation_id;
    if (viewing) { state.chatJob = null; state.chatId = job.convId; }
  } else if (viewing && !ok) state.chatJob = null;
  if (ok && !viewing) state.unseen.add(job.convId);
  if (!$("#cg") || !state.chatUI) return; // đang ở trang khác; câu trả lời đã được lưu ở server
  const ui = state.chatUI;
  if (viewing) {
    const pending = $("#pending");
    if (pending) {
      pending.outerHTML = msgHtml({ role: "assistant", content: res.answer, tools: res.tools_used, error: !!res.error });
      if (!ok) ui.q.value = job.text; // trả lại câu hỏi để gửi lại
      ui.scroll();
    } else if (ok) await ui.open(job.convId);
    ui.setBusy();
  } else if (ok) toast("Trợ lý đã trả lời xong một đoạn chat khác.");
  await ui.refreshList();
}

const CHAT_SUGGESTIONS = [
  "Tóm tắt cơ cấu tổ chức công ty và các điểm cần lưu ý",
  "Những vị trí nào đang trống và mức độ ưu tiên tuyển dụng?",
  "Đánh giá rủi ro từ việc kiêm nhiệm hiện nay",
  "Dữ liệu nào còn thiếu để AI có thể đề xuất tối ưu nhân sự?",
];

// Nhóm lịch sử chat theo thời gian như ChatGPT/Claude
function convGroup(ts) {
  const d = new Date(String(ts).replace(" ", "T"));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.floor((today - new Date(d).setHours(0, 0, 0, 0)) / 86400000);
  if (days <= 0) return "Hôm nay";
  if (days === 1) return "Hôm qua";
  if (days < 7) return "7 ngày trước";
  if (days < 30) return "30 ngày trước";
  return `Tháng ${d.getMonth() + 1}/${d.getFullYear()}`;
}

// Tên công cụ AI -> mô tả tiếng Việt (không hiện tên kỹ thuật cho TGĐ)
const TOOL_LABELS = {
  get_org_overview: "sơ đồ tổ chức",
  get_unit_detail: "thông tin đơn vị",
  search: "tìm kiếm chung",
  list_employees: "danh sách nhân sự",
  get_org_insights: "chỉ số tổ chức",
  get_process: "quy trình",
  list_documents: "kho tài liệu",
  search_documents: "tìm trong tài liệu",
  read_document: "nội dung tài liệu",
  list_targets: "mục tiêu doanh thu",
  tao_file: "tạo file",
};

function msgHtml(m) {
  if (m.role === "user") return `<div class="msg user">${esc(m.content)}</div>`;
  const body = window.marked ? marked.parse(esc(m.content).replace(/&gt;/g, ">")) : esc(m.content);
  const labels = [...new Set((m.tools || []).map((t) => TOOL_LABELS[t] || "dữ liệu công ty"))];
  const tools = labels.length ? `<div class="tools">Đã tra cứu: ${labels.map(esc).join(", ")}</div>` : "";
  return `<div class="msg assistant ${m.error ? "error" : ""}"><div class="av">AZB</div><div class="body">${body}${tools}</div></div>`;
}

// ---------------- Tab trong trang đơn vị ----------------
const UNIT_TABS = {
  async org(body, u) {
    const emps = await api("/api/employees");
    body.innerHTML = `
      <div class="toolbar"><h3 style="margin:0">Chức danh & người phụ trách</h3><button class="primary" id="add-pos">+ Thêm chức danh</button></div>
      ${u.positions.length ? `
        <table>
          <tr><th>Chức danh</th><th>Người giữ</th><th>Định biên</th><th>Ghi chú</th><th></th></tr>
          ${u.positions.map((p) => `
            <tr>
              <td>${esc(p.title)} ${p.title_code ? `<span class="badge">${esc(p.title_code)}</span>` : ""} ${p.is_head ? '<span class="badge ok">Phụ trách</span>' : ""}</td>
              <td>${p.employee_name ? esc(p.employee_name) + (p.employee_verified ? "" : ' <span class="badge warn">?</span>') : '<span class="badge warn">TBA – đang trống</span>'}</td>
              <td class="num">${p.headcount}</td>
              <td class="muted">${esc(p.notes || "")}</td>
              <td><button class="link" data-edit="${p.id}">Sửa</button> · <button class="link danger" data-del="${p.id}">Xoá</button></td>
            </tr>`).join("")}
        </table>` : '<div class="empty">Chưa có chức danh nào.</div>'}
      ${(() => {
        const members = sortByRank(emps.filter((e) => e.unit_id === u.id && e.status !== "inactive"));
        return members.length ? `
          <h3 style="margin-top:20px">Nhân sự theo danh sách HCNS (${members.length})</h3>
          <table>
            <tr><th style="width:90px">Mã NV</th><th>Họ tên</th><th>Chức danh</th><th>Ngạch</th></tr>
            ${members.map((e, i) => `<tr><td><span class="badge">${esc(e.employee_code || "")}</span></td>
              <td><b>${esc(e.full_name)}</b> ${i === 0 && isManager(e) ? '<span class="badge ok">Phụ trách</span>' : ""}</td>
              <td>${esc(e.job_title || "")}</td><td class="muted">${esc(e.grade || "")}</td></tr>`).join("")}
          </table>` : "";
      })()}
      <h3 style="margin-top:20px">Đơn vị trực thuộc</h3>
      ${u.children.length ? u.children.map((c) => `<button class="ghost" style="margin:0 6px 6px 0" onclick="go('units',{unitId:${c.id}})">${esc(c.name)}</button>`).join("")
        : '<div class="muted">Không có.</div>'}`;
    const form = (p) => openForm(p.id ? "Sửa chức danh" : "Thêm chức danh", [
      { name: "title", label: "Chức danh", required: true, placeholder: "VD: Trưởng phòng" },
      { name: "title_code", label: "Mã chức danh", placeholder: "TP, PP, GĐ, NV..." },
      { name: "employee_id", label: "Người giữ", type: "select", numeric: true, options: [["", "— Đang trống (TBA) —"], ...emps.map((e) => [e.id, e.full_name])] },
      { name: "is_head", label: "Là người phụ trách đơn vị?", type: "select", numeric: true, options: [[0, "Không"], [1, "Có"]] },
      { name: "headcount", label: "Định biên", type: "number", default: 1 },
      { name: "notes", label: "Ghi chú", type: "textarea" },
    ], p, (data) => (p.id ? api(`/api/positions/${p.id}`, { method: "PUT", body: data }) : api("/api/positions", { method: "POST", body: { ...data, unit_id: u.id } })));
    $("#add-pos").onclick = () => form({});
    body.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(u.positions.find((p) => p.id == b.dataset.edit))));
    body.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => confirmDelete("positions", b.dataset.del, "chức danh này")));
  },

  process(body, u) {
    body.innerHTML = `
      <div class="toolbar"><h3 style="margin:0">Quy trình vận hành / ISO</h3><button class="primary" id="add-proc">+ Thêm quy trình</button></div>
      ${u.processes.length ? u.processes.map((p) => `
        <div class="card" style="margin-bottom:10px">
          <div class="toolbar">
            <div><b>${esc(p.code || "")} ${esc(p.name)}</b> <span class="badge">${PROCESS_STATUS[p.status] || p.status}</span>
              ${p.version ? `<span class="badge">v${esc(p.version)}</span>` : ""}</div>
            <div><button class="link" data-edit="${p.id}">Sửa</button> · <button class="link danger" data-del="${p.id}">Xoá</button></div>
          </div>
          <dl class="kv">
            ${p.purpose ? `<dt>Mục đích</dt><dd>${esc(p.purpose)}</dd>` : ""}
            ${p.owner ? `<dt>Chủ trì</dt><dd>${esc(p.owner)}</dd>` : ""}
            ${p.related_units ? `<dt>Phối hợp</dt><dd>${esc(p.related_units)}</dd>` : ""}
            ${p.iso_clause ? `<dt>Điều khoản ISO</dt><dd>${esc(p.iso_clause)}</dd>` : ""}
            ${p.effective_date ? `<dt>Hiệu lực</dt><dd>${esc(p.effective_date)}</dd>` : ""}
          </dl>
          ${p.content ? `<details><summary>Nội dung các bước</summary><div class="process-content">${esc(p.content)}</div></details>` : ""}
        </div>`).join("") : '<div class="empty">Chưa có quy trình. Bấm “Thêm quy trình” để nhập khi có dữ liệu.</div>'}`;
    const form = (p) => openForm(p.id ? "Sửa quy trình" : "Thêm quy trình", [
      { name: "code", label: "Mã quy trình", placeholder: "VD: QT-HCNS-01" },
      { name: "name", label: "Tên quy trình", required: true },
      { name: "version", label: "Phiên bản" },
      { name: "status", label: "Trạng thái", type: "select", options: Object.entries(PROCESS_STATUS), default: "draft" },
      { name: "iso_clause", label: "Điều khoản ISO liên quan", placeholder: "VD: ISO 9001:2015 – 7.2" },
      { name: "owner", label: "Chức danh chủ trì" },
      { name: "related_units", label: "Đơn vị phối hợp" },
      { name: "effective_date", label: "Ngày hiệu lực", type: "date" },
      { name: "purpose", label: "Mục đích, phạm vi", type: "textarea" },
      { name: "content", label: "Các bước thực hiện (ai – làm gì – đầu vào – đầu ra – thời hạn)", type: "textarea" },
    ], p, (data) => (p.id ? api(`/api/processes/${p.id}`, { method: "PUT", body: data }) : api("/api/processes", { method: "POST", body: { ...data, unit_id: u.id } })));
    $("#add-proc").onclick = () => form({});
    body.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(u.processes.find((p) => p.id == b.dataset.edit))));
    body.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => confirmDelete("processes", b.dataset.del, "quy trình này")));
  },

  target(body, u) {
    body.innerHTML = `
      <div class="toolbar"><h3 style="margin:0">Mục tiêu doanh thu, doanh số</h3><button class="primary" id="add-tg">+ Thêm mục tiêu</button></div>
      ${u.targets.length ? `
        <table>
          <tr><th>Kỳ</th><th>Chỉ tiêu</th><th class="num">Mục tiêu</th><th class="num">Thực hiện</th><th class="num">% đạt</th><th>Ghi chú</th><th></th></tr>
          ${u.targets.map((t) => `
            <tr>
              <td>${esc(t.period)}</td>
              <td>${esc(t.metric_name || METRICS[t.metric] || t.metric)}</td>
              <td class="num">${fmtNum(t.target_value)} <span class="muted">${esc(t.unit_label || "")}</span></td>
              <td class="num">${fmtNum(t.actual_value)}</td>
              <td class="num">${t.target_value && t.actual_value != null ? Math.round((t.actual_value / t.target_value) * 100) + "%" : "—"}</td>
              <td class="muted">${esc(t.notes || "")}</td>
              <td><button class="link" data-edit="${t.id}">Sửa</button> · <button class="link danger" data-del="${t.id}">Xoá</button></td>
            </tr>`).join("")}
        </table>` : '<div class="empty">Chưa có mục tiêu. Bấm “Thêm mục tiêu” để nhập khi có số liệu.</div>'}`;
    const form = (t) => openForm(t.id ? "Sửa mục tiêu" : "Thêm mục tiêu", [
      { name: "period", label: "Kỳ", required: true, placeholder: "2026, 2026-Q4 hoặc 2026-10" },
      { name: "metric", label: "Loại chỉ tiêu", type: "select", options: Object.entries(METRICS), default: "doanh_thu" },
      { name: "metric_name", label: "Tên chỉ tiêu (nếu là chỉ tiêu khác)" },
      { name: "target_value", label: "Giá trị mục tiêu", type: "number" },
      { name: "actual_value", label: "Giá trị thực hiện", type: "number" },
      { name: "unit_label", label: "Đơn vị tính", default: "VNĐ" },
      { name: "notes", label: "Ghi chú", type: "textarea" },
    ], t, (data) => (t.id ? api(`/api/targets/${t.id}`, { method: "PUT", body: data }) : api("/api/targets", { method: "POST", body: { ...data, unit_id: u.id } })));
    $("#add-tg").onclick = () => form({});
    body.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(u.targets.find((t) => t.id == b.dataset.edit))));
    body.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => confirmDelete("targets", b.dataset.del, "mục tiêu này")));
  },

  async docs(body, u) {
    const [meta, units] = await Promise.all([api("/api/documents/meta"), api("/api/units")]);
    body.innerHTML = `
      <div class="toolbar"><h3 style="margin:0">Tài liệu của đơn vị</h3>${can("docs_edit") ? DOC_ACTIONS : ""}</div>
      ${u.documents.length ? docTable(u.documents, false) : '<div class="empty">Chưa có tài liệu. Tải lên quy trình ISO, hướng dẫn, biểu mẫu của đơn vị.</div>'}`;
    if (can("docs_edit")) {
      $("#up-doc").onclick = () => uploadForm(meta, units, u.id);
      $("#url-doc").onclick = () => urlLearnForm(units, u.id);
    }
    bindDocActions(body, meta, units);
    pollIfProcessing(u.documents);
  },

  info(body, u) {
    body.innerHTML = `
      <dl class="kv">
        <dt>Mã</dt><dd>${esc(u.code)}</dd>
        <dt>Tên đầy đủ</dt><dd>${esc(u.full_name || "—")}</dd>
        <dt>Loại</dt><dd>${UNIT_TYPES[u.unit_type] || esc(u.unit_type)}</dd>
        <dt>Chức năng, nhiệm vụ</dt><dd>${u.functions ? esc(u.functions) : '<span class="muted">Chưa nhập – bấm “Sửa” để bổ sung.</span>'}</dd>
        <dt>Ghi chú</dt><dd>${esc(u.notes || "—")}</dd>
      </dl>`;
  },
};

// ---------------- Form đơn vị / nhân sự ----------------
function unitForm(units, u) {
  openForm(u.id ? "Sửa đơn vị" : "Thêm đơn vị", [
    { name: "code", label: "Mã đơn vị", required: true, placeholder: "VD: P-HCNS" },
    { name: "name", label: "Tên hiển thị", required: true },
    { name: "full_name", label: "Tên đầy đủ / giải nghĩa viết tắt" },
    { name: "unit_type", label: "Loại", type: "select", options: Object.entries(UNIT_TYPES), default: "department" },
    { name: "parent_id", label: "Trực thuộc", type: "select", numeric: true, options: [["", "— Không —"], ...units.filter((x) => x.id !== u.id).map((x) => [x.id, x.name])] },
    { name: "color_group", label: "Nhóm", type: "select", options: Object.entries(COLOR_GROUPS) },
    { name: "verified", label: "Thông tin đã xác nhận?", type: "select", numeric: true, options: [[1, "Đã xác nhận"], [0, "Cần xác nhận"]], default: 1 },
    { name: "functions", label: "Chức năng, nhiệm vụ", type: "textarea" },
    { name: "notes", label: "Ghi chú", type: "textarea" },
  ], u, async (data) => {
    const saved = u.id ? await api(`/api/units/${u.id}`, { method: "PUT", body: data }) : await api("/api/units", { method: "POST", body: data });
    state.unitId = saved.id;
  });
}

async function employeeForm(e) {
  const isNew = !e.id;
  const units = await api("/api/units");
  const unitOptions = [["", "— Chọn phòng ban —"], ...units.map((u) => [u.id, u.name])];
  openForm(isNew ? "Thêm nhân sự" : "Sửa nhân sự", [
    { name: "employee_code", label: "Mã nhân viên", placeholder: "VD: NV23001" },
    { name: "full_name", label: "Họ tên nhân viên", required: true },
    { name: "unit_id", label: "Phòng ban / Công trình", type: "select", numeric: true, options: unitOptions },
    { name: "grade", label: "Chức vụ", type: "select", options: GRADES.map((g) => [g, g]), default: "Nhân viên" },
    { name: "job_title", label: "Chức danh cụ thể", placeholder: "VD: Trưởng nhóm IT Helpdesk, NV Kế toán..." },
    ...(isNew ? [{ name: "title_code", label: "Vị trí trên sơ đồ tổ chức", type: "select", options: [["", "— Không gán (nhân viên thường) —"], ...TITLES], default: "" }] : []),
    { name: "email", label: "Email", type: "email" },
    { name: "phone", label: "Điện thoại" },
    { name: "joined_date", label: "Ngày vào công ty", type: "date" },
    { name: "birth_date", label: "Ngày sinh", type: "date" },
    { name: "contract_term", label: "Hợp đồng lao động" },
    { name: "status", label: "Trạng thái", type: "select", options: [["active", "Đang làm việc"], ["inactive", "Đã nghỉ"]] },
    { name: "verified", label: "Họ tên đã xác nhận?", type: "select", numeric: true, options: [[1, "Đã xác nhận"], [0, "Cần bổ sung"]], default: 1 },
    { name: "notes", label: "Ghi chú", type: "textarea" },
  ], e, async (data) => {
    // Đổi đơn vị thì nhóm hiển thị ở trang Nhân sự đổi theo (lấy tên nhóm của đồng nghiệp cùng đơn vị nếu có)
    if (data.unit_id && data.unit_id !== e.unit_id) {
      const peer = (await api("/api/employees")).find((x) => x.unit_id === data.unit_id && x.hr_department);
      data.hr_department = peer ? peer.hr_department : units.find((u) => u.id === data.unit_id).name;
      data.hr_division = peer ? peer.hr_division : null;
    }
    if (!isNew) return api(`/api/employees/${e.id}`, { method: "PUT", body: data });
    const { title_code, ...emp } = data;
    if (!emp.unit_id) throw new Error("Chưa chọn phòng ban");
    const saved = await api("/api/employees", { method: "POST", body: emp });
    if (!title_code) return saved;
    const unit_id = emp.unit_id;
    // Gán vào chức danh đang trống cùng loại trong phòng ban; nếu không có thì tạo chức danh mới
    const unit = await api(`/api/units/${unit_id}`);
    const vacant = unit.positions.find((p) => !p.employee_id && p.title_code === title_code);
    if (vacant) return api(`/api/positions/${vacant.id}`, { method: "PUT", body: { employee_id: saved.id } });
    const title = TITLES.find(([code]) => code === title_code)[1];
    return api("/api/positions", { method: "POST", body: { unit_id, title, title_code, employee_id: saved.id } });
  });
}

boot();

// ---------------- Tài liệu ----------------
// Tô đậm phần khớp, cùng quy tắc với backend: từ gõ có dấu khớp đúng dấu, gõ không dấu khớp mọi dấu
function hlDoc(text, query) {
  const nfc = (s) => String(s ?? "").normalize("NFC").toLowerCase();
  const terms = (nfc(query).match(/[\p{L}\p{N}_]+/gu) || []).filter((w) => w.length > 1).map((w) => [w, norm(w) !== w]);
  const chars = [...String(text ?? "").normalize("NFC")];
  const flats = [[], []]; // [không dấu, giữ dấu] -> { s, at }
  const build = (conv) => { let s = ""; const at = []; chars.forEach((c, i) => { const n = conv(c); s += n; for (let k = 0; k < n.length; k++) at.push(i); }); return { s, at }; };
  const loose = build(norm), strictF = build((c) => c.toLowerCase());
  const word = /[\p{L}\p{N}_]/u;
  const on = new Array(chars.length).fill(false);
  terms.forEach(([w, strict]) => {
    const { s, at } = strict ? strictF : loose;
    const needle = strict ? w : norm(w);
    for (let p = s.indexOf(needle); p !== -1; p = s.indexOf(needle, p + 1)) {
      if ((p > 0 && word.test(s[p - 1])) || (p + needle.length < s.length && word.test(s[p + needle.length]))) continue;
      for (let k = p; k < p + needle.length; k++) on[at[k]] = true;
    }
  });
  return chars.map((c, i) => (on[i] && !on[i - 1] ? "<mark>" : "") + esc(c) + (on[i] && !on[i + 1] ? "</mark>" : "")).join("");
}

// Link mở trực tiếp: trang web -> URL gốc; file -> xem ngay trong tab mới
// (PDF/ảnh/txt hiển thị nguyên bản, Excel/Word được máy chủ dựng thành trang web)
function docHref(d) {
  if (/^https?:\/\//i.test(d.filename || "")) return d.filename;
  return `/api/documents/${d.id}/file?inline=1`;
}

const isAiPdf = (d) => /AI/.test(d.extract_note || "") && /\.pdf$/i.test(d.filename || "") && d.extract_status === "ok";
function reviewLabel(d) {
  const done = d.reviewed_pages || 0, total = d.page_count || 0;
  if (total && done >= total) return "✓ Đã đối chiếu đủ";
  return done ? `Đối chiếu (${done}/${total} trang)` : "Đối chiếu bản gốc";
}

// Đối chiếu từng trang: ảnh trang gốc bên trái, chữ AI đã đọc bên phải; người duyệt xác nhận đúng hoặc sửa tại chỗ
async function reviewDoc(docId, onClose) {
  const modal = $("#modal"), body = $("#modal-body");
  let data;
  try { data = await api(`/api/documents/${docId}/review`); } catch (e) { toast(e.message, "err"); return; }
  const editable = can("docs_edit");
  let cur = Math.max(1, (data.pages.find((p) => !p.status && p.flags.length) || data.pages.find((p) => !p.status) || data.pages[0]).page);
  $("#modal-title").textContent = `Đối chiếu: ${data.title}`;
  modal.classList.add("wide");
  $("#modal-ok").textContent = "Đóng";
  $("#modal-cancel").style.display = "none";
  $("#modal-form").onsubmit = (e) => { e.preventDefault(); modal.close(); };
  modal.addEventListener("close", () => { modal.classList.remove("wide"); $("#modal-cancel").style.display = ""; onClose && onClose(); }, { once: true });
  const chip = (p) => `<button type="button" class="rv-chip ${p.status || (p.flags.length ? "flag" : "")} ${p.page === cur ? "cur" : ""}" data-pg="${p.page}"
      title="${esc(p.status === "verified" ? "Đã xác nhận đúng" : p.status === "edited" ? "Đã sửa" : p.flags.join("; ") || "Chưa đối chiếu")}">${p.page}</button>`;
  const draw = () => {
    const p = data.pages.find((x) => x.page === cur);
    const done = data.pages.filter((x) => x.status).length;
    body.innerHTML = `<div class="muted" style="margin-bottom:8px"><b>${done}/${data.total}</b> trang đã đối chiếu ·
        <span class="rv-chip verified">đúng</span> <span class="rv-chip edited">đã sửa</span> <span class="rv-chip flag">nghi ngờ</span> <span class="rv-chip">chưa xem</span></div>
      <div class="rv-chips">${data.pages.map(chip).join("")}</div>
      ${p.flags.length ? `<div class="unread-banner" style="margin-top:10px">⚠ ${p.flags.map(esc).join("; ")}</div>` : ""}
      <div class="rv-grid">
        <div class="rv-img"><img src="/api/documents/${docId}/page/${cur}.png" alt="Trang ${cur} bản gốc"></div>
        <div><textarea id="rv-text" class="rv-text" ${editable ? "" : "readonly"}>${esc(p.text)}</textarea>
          <div class="rv-bar">
            <button type="button" class="ghost" id="rv-prev" ${cur <= 1 ? "disabled" : ""}>◀ Trước</button>
            <span class="muted">Trang ${cur}/${data.total}</span>
            <button type="button" class="ghost" id="rv-next" ${cur >= data.total ? "disabled" : ""}>Sau ▶</button>
            ${editable ? `<button type="button" class="primary" id="rv-ok">${"✓ Chữ khớp bản gốc – sang trang sau"}</button>
            ${p.status ? `<button type="button" class="ghost" id="rv-undo" title="${p.status === "edited" ? "Bỏ dấu đã đối chiếu (chữ đã sửa vẫn giữ nguyên)" : "Bỏ dấu đã đối chiếu"}">↩ Bỏ xác nhận trang này</button>` : ""}` : ""}
          </div></div></div>`;
    body.querySelectorAll(".rv-chips [data-pg]").forEach((b) => (b.onclick = () => { cur = +b.dataset.pg; draw(); }));
    $("#rv-prev").onclick = () => { cur--; draw(); };
    $("#rv-next").onclick = () => { cur++; draw(); };
    const undo = $("#rv-undo");
    if (undo) undo.onclick = async () => {
      undo.disabled = true;
      try { await api(`/api/documents/${docId}/review/${cur}`, { method: "DELETE" }); p.status = null; draw(); }
      catch (e) { toast(e.message, "err"); undo.disabled = false; }
    };
    const ok = $("#rv-ok");
    if (ok) ok.onclick = async () => {
      const text = $("#rv-text").value;
      ok.disabled = true;
      try {
        const r = await api(`/api/documents/${docId}/review/${cur}`, { method: "PUT", body: text.trim() !== p.text.trim() ? { text } : {} });
        p.status = r.status; p.text = text.trim(); p.flags = r.status === "edited" ? [] : p.flags;
        if (cur < data.total) cur++;
        draw();
      } catch (e) { toast(e.message, "err"); ok.disabled = false; }
    };
  };
  draw();
  modal.showModal();
}

function docTable(docs, showUnit, query = "") {
  if (!docs.length) return '<div class="empty">Chưa có tài liệu nào.</div>';
  return `<table>
    <tr><th>Tài liệu</th>${showUnit ? "<th>Đơn vị</th>" : ""}<th>Loại</th><th>Trạng thái</th><th>Tải lên</th><th></th></tr>
    ${docs.map((d) => {
      const [lbl, cls] = DOC_STATUS[d.extract_status] || [d.extract_status, ""];
      return `<tr${DOC_UNREAD.has(d.extract_status) ? ' class="row-bad"' : ""}>
        <td>${docHref(d) ? `<a class="doc-title" href="${esc(docHref(d))}" target="_blank" rel="noopener">` : ""}<b>${query ? hlDoc(`${d.code || ""} ${d.title}`.trim(), query) : `${esc(d.code || "")} ${esc(d.title)}`}</b>${docHref(d) ? "</a>" : ""}${d.version ? ` <span class="badge">v${esc(d.version)}</span>` : ""}${d.access_level && d.access_level !== "internal" ? ` <span class="badge ${d.access_level === "secret" || d.access_level === "restricted" ? "warn" : ""}">${esc(ACCESS_LABELS[d.access_level] || d.access_level)}</span>` : ""}
          ${query ? "" : `<div class="muted">${esc(d.filename)} ${d.page_count ? "· " + d.page_count + " trang" : ""} ${fmtSize(d.size_bytes)}</div>`}
          ${query && d.snippet ? `<div class="doc-snippet">${hlDoc(d.snippet, query)}</div>` : ""}
          ${d.extract_note ? `<div style="color:var(${DOC_UNREAD.has(d.extract_status) ? "--danger" : "--warn"})">${esc(d.extract_note)}</div>` : ""}</td>
        ${showUnit ? `<td>${d.unit_id ? `<button class="link" onclick="go('units',{unitId:${d.unit_id}, unitTab:'docs'})">${esc(d.unit_name)}</button>` : "Chung"}</td>` : ""}
        <td>${esc(DOC_LABELS[d.doc_type] || d.doc_type)}</td>
        <td><span class="badge ${cls}">${lbl}</span></td>
        <td class="muted">${esc((d.uploaded_at || "").slice(0, 16))}</td>
        <td style="white-space:nowrap">${isAiPdf(d) ? `<button class="link" data-review-doc="${d.id}">${reviewLabel(d)}</button> · ` : ""}<button class="link" data-view-doc="${d.id}">Xem chữ</button> ·
          <a class="link" href="/api/documents/${d.id}/file" target="_blank">Tải về</a>
          ${can("docs_edit") ? `<span class="doc-edit">${query ? `<details class="doc-more"><summary>⋯</summary><div>` : " · "}<button class="link" data-edit-doc="${d.id}">Sửa</button> ·
          <button class="link" data-reproc="${d.id}">Đọc lại</button> ·
          <button class="link danger" data-del-doc="${d.id}">Xoá</button>${query ? "</div></details>" : ""}</span>` : ""}</td>
      </tr>`;
    }).join("")}
  </table>`;
}

function uploadForm(meta, units, unitId) {
  openForm("Tải tài liệu lên", [
    { name: "file", label: "File", type: "file", required: true, accept: meta.allowed_ext.join(",") },
    { name: "title", label: "Tên tài liệu (để trống = lấy theo tên file)" },
    { name: "code", label: "Mã tài liệu", placeholder: "VD: QT-HCNS-01" },
    { name: "version", label: "Phiên bản / lần ban hành" },
    { name: "doc_type", label: "Loại", type: "select", options: Object.entries(meta.types), default: "quy_trinh" },
    { name: "unit_id", label: "Đơn vị chủ quản", type: "select", options: [["", "— Tài liệu chung công ty —"], ...units.map((u) => [u.id, u.name])] },
    { name: "access_level", label: "Độ mật (ai được xem, kể cả qua trợ lý AI)", type: "select", options: meta.levels, default: meta.default_level },
  ], { unit_id: unitId ?? "" }, (d) => {
    const fd = new FormData();
    Object.entries(d).forEach(([k, v]) => v !== "" && v != null && fd.append(k, v));
    return api("/api/documents", { method: "POST", body: fd });
  });
}

function bindDocActions(el, meta, units) {
  el.querySelectorAll("[data-del-doc]").forEach((b) => (b.onclick = () => confirmDelete("documents", b.dataset.delDoc, "tài liệu này")));
  el.querySelectorAll("[data-reproc]").forEach((b) => (b.onclick = async () => {
    try { await api(`/api/documents/${b.dataset.reproc}/reprocess`, { method: "POST" }); render(); } catch (e) { toast(e.message, "err"); }
  }));
  el.querySelectorAll("[data-edit-doc]").forEach((b) => (b.onclick = async () => {
    const d = await api(`/api/documents/${b.dataset.editDoc}`);
    openForm("Sửa thông tin tài liệu", [
      { name: "title", label: "Tên tài liệu", required: true },
      { name: "code", label: "Mã tài liệu" },
      { name: "version", label: "Phiên bản" },
      { name: "doc_type", label: "Loại", type: "select", options: Object.entries(meta.types) },
      { name: "unit_id", label: "Đơn vị chủ quản", type: "select", numeric: true, options: [["", "— Tài liệu chung —"], ...units.map((u) => [u.id, u.name])] },
      { name: "access_level", label: "Độ mật (ai được xem, kể cả qua trợ lý AI)", type: "select", options: d.access_level === "secret" && !meta.levels.some(([k]) => k === "secret") ? [["secret", "Mật (chỉ Ban TGĐ/Admin)"]] : meta.levels },
    ], d, (data) => api(`/api/documents/${d.id}`, { method: "PUT", body: data }));
  }));
  el.querySelectorAll("[data-review-doc]").forEach((b) => (b.onclick = () => reviewDoc(b.dataset.reviewDoc, () => render())));
  el.querySelectorAll("[data-view-doc]").forEach((b) => (b.onclick = async () => {
    const d = await api(`/api/documents/${b.dataset.viewDoc}`);
    $("#modal-title").textContent = d.title;
    $("#modal-body").innerHTML = `<p class="muted">Nội dung AI sẽ đọc (${fmtNum(d.char_count)} ký tự)</p>
      <div class="process-content" style="max-height:60vh;overflow:auto">${esc(d.content || "Chưa có nội dung – tài liệu chưa được đọc xong hoặc bị lỗi.")}</div>`;
    $("#modal-form").onsubmit = (e) => { e.preventDefault(); $("#modal").close(); };
    $("#modal-cancel").onclick = () => $("#modal").close();
    $("#modal").showModal();
  }));
}

function pollIfProcessing(docs) {
  if (docs.some((d) => d.extract_status === "pending" || d.extract_status === "processing")) {
    pollTimer = setTimeout(() => { if (!$("#modal").open) render(); }, 3000);
  }
}


// Học từ URL: bước 1 dán URL -> AI đọc và tóm tắt; bước 2 xem trước và duyệt rồi mới lưu vào kho
function urlLearnForm(units, unitId) {
  const modal = $("#modal"), body = $("#modal-body"), ok = $("#modal-ok"), cancel = $("#modal-cancel"), form = $("#modal-form");
  $("#modal-title").textContent = "Học nội dung từ URL";
  body.innerHTML = `<div class="field"><label>Địa chỉ trang web công khai (hoặc link file PDF/DOCX/XLSX)</label>
      <input name="url" type="url" placeholder="https://..." required></div>
    <div class="field"><label>Đơn vị chủ quản</label>
      <select name="unit_id">${[["", "— Tài liệu chung công ty —"], ...units.map((u) => [u.id, u.name])]
        .map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(unitId ?? "") ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></div>
    <div id="url-status" class="muted"></div>`;
  ok.textContent = "Đọc trang này";
  ok.disabled = false;
  cancel.onclick = () => modal.close();
  let draft = null;
  const discard = () => { if (draft) api(`/api/documents/from-url/${draft.draft_id}`, { method: "DELETE" }).catch(() => {}); };
  form.onsubmit = async (e) => {
    e.preventDefault();
    ok.disabled = true;
    try {
      if (!draft) {
        $("#url-status").textContent = "Đang tải trang và nhờ AI đọc, vui lòng đợi...";
        draft = await api("/api/documents/from-url/preview", { method: "POST", body: { url: form.elements.url.value } });
        const unit = form.elements.unit_id.value;
        body.innerHTML = `<div class="field"><label>Tên tài liệu</label><input name="title" value="${esc(draft.title)}"></div>
          <p class="muted">Nguồn: <a class="link" href="${esc(draft.url)}" target="_blank" rel="noopener">${esc(draft.url)}</a> · ${fmtNum(draft.char_count)} ký tự</p>
          <b>Tóm tắt của AI</b>
          <div class="process-content">${draft.summary ? esc(draft.summary) : "Chưa tạo được tóm tắt (chưa cấu hình khoá AI hoặc AI đang bận) – nội dung vẫn được lưu để tra cứu."}</div>
          <details style="margin-top:10px"><summary>Xem nội dung đã đọc${draft.truncated ? " (đoạn đầu)" : ""}</summary>
            <div class="process-content" style="max-height:40vh;overflow:auto">${esc(draft.preview)}</div></details>
          <input type="hidden" name="unit_id" value="${esc(unit)}">`;
        ok.textContent = "Lưu vào kho tài liệu";
      } else {
        await api("/api/documents/from-url", { method: "POST", body: {
          draft_id: draft.draft_id, title: form.elements.title.value, unit_id: form.elements.unit_id.value === "" ? null : Number(form.elements.unit_id.value) } });
        draft = null;
        modal.close();
        render();
      }
    } catch (err) {
      $("#url-status") ? ($("#url-status").textContent = err.message) : toast(err.message, "err");
      if ($("#url-status")) $("#url-status").style.color = "var(--warn)";
    } finally {
      ok.disabled = false;
    }
  };
  modal.addEventListener("close", () => { discard(); ok.textContent = "Lưu"; }, { once: true });
  modal.showModal();
}
