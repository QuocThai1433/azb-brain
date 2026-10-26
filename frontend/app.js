// AZB Brain – giao diện quản trị (vanilla JS, không cần build)

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtNum = (n) => (n == null ? "—" : Number(n).toLocaleString("vi-VN"));

const UNIT_TYPES = { board: "HĐQT", executive: "Ban điều hành", division: "Khối", department: "Phòng/Ban", committee: "Ban chuyên trách", project: "Dự án" };
const COLOR_GROUPS = { exec: "Điều hành", hr: "Nhân sự - Hành chính", ops: "Vận hành", finance: "Tài chính", technical: "Kinh tế - Kỹ thuật", construction: "Thi công / Xây lắp", commercial: "Thương mại" };
const METRICS = { doanh_so: "Doanh số", doanh_thu: "Doanh thu", loi_nhuan: "Lợi nhuận", dong_tien: "Dòng tiền", okr_du_an: "OKRs dự án", khac: "Chỉ tiêu khác" };
const PROCESS_STATUS = { draft: "Nháp", active: "Đang áp dụng", retired: "Hết hiệu lực" };
const PROPOSAL_STATUS = { new: "Mới", approved: "Đã duyệt", in_progress: "Đang thực hiện", review: "Chờ nghiệm thu", done: "Hoàn thành", dropped: "Không thực hiện" };
const PROPOSAL_CLASS = { new: "brand", approved: "ok", in_progress: "warn", review: "brand", done: "ok", dropped: "" };
const TITLES = [["CT", "Chủ tịch HĐQT"], ["TGĐ", "Tổng Giám đốc"], ["PTGĐ", "Phó Tổng Giám đốc"], ["GĐK", "Giám đốc Khối"], ["GĐ", "Giám đốc"],
  ["TB", "Trưởng ban"], ["PB", "Phó ban"], ["PT", "Phụ trách điều hành"], ["TP", "Trưởng phòng"], ["PP", "Phó phòng"], ["TBP", "Trưởng bộ phận"], ["NV", "Nhân viên"]];
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
  plus: '<path d="M12 5v14M5 12h14"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
  left: '<path d="M15 6l-6 6 6 6"/>',
  right: '<path d="m9 6 6 6-6 6"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
};
const icon = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const FEATURE_LABELS = { import_hr: "Nhập file HCNS", docs_view: "Xem tài liệu", docs_edit: "Sửa tài liệu (thêm/sửa)", docs_delete: "Xoá tài liệu", docs_download: "Tải file gốc tài liệu", insights: "Xem Phân tích", ai_use: "Dùng trợ lý AI" };
const PERM_TEMPLATES = {
  none: ["Không cấp thêm", []],
  docs: ["Xem tài liệu", ["docs_view", "docs_download"]],
  hr: ["Nhân viên HCNS", ["import_hr", "docs_view", "docs_download"]],
  lead: ["Trưởng phòng / quản lý", ["docs_view", "docs_download", "docs_edit", "docs_delete", "insights", "ai_use"]],
};
const PERM_GROUPS = [["Tài liệu", ["docs_view", "docs_edit", "docs_delete", "docs_download"]], ["Khác", ["import_hr", "insights", "ai_use"]]];
const DOC_DEPENDENTS = ["docs_edit", "docs_delete", "docs_download"];  // cần xem được tài liệu mới dùng được
const permFields = (on = []) => PERM_GROUPS.flatMap(([title, fs]) => [
  { type: "info", group: true, label: title },
  ...fs.map((f) => ({ name: f, label: FEATURE_LABELS[f], type: "check", compact: true, default: on.includes(f) })),
]);
const permValues = (granted) => Object.fromEntries(Object.keys(FEATURE_LABELS).map((f) =>
  [f, granted.includes(f) || (f === "docs_view" && DOC_DEPENDENTS.some((g) => granted.includes(g)))]));
const pickedFeatures = (d) => Object.keys(FEATURE_LABELS).filter((f) => d[f]);
// Mẫu quyền tick nhanh; tick sửa/xoá/tải thì tự tick Xem, bỏ Xem thì bỏ các quyền phụ thuộc
function bindPermForm() {
  const form = $("#modal-form"), el = form.elements;
  el._tpl.onchange = (e) => {
    const on = PERM_TEMPLATES[e.target.value][1];
    Object.keys(FEATURE_LABELS).forEach((f) => (el[f].checked = on.includes(f)));
  };
  form.onchange = (e) => {
    if (!el.docs_view) return;
    if (e.target.name === "docs_view" && !e.target.checked) {
      DOC_DEPENDENTS.forEach((f) => (el[f].checked = false));
      hideCheckNote(e.target.closest(".check"));
    }
    else if (DOC_DEPENDENTS.includes(e.target.name) && !e.target.checked && !DOC_DEPENDENTS.some((f) => el[f].checked)) hideCheckNote(el.docs_view.closest(".check"));
    else if (DOC_DEPENDENTS.includes(e.target.name) && e.target.checked && !el.docs_view.checked) {
      el.docs_view.checked = true;
      flashCheck(el.docs_view.closest(".check"), "Tự bật: cần xem được tài liệu mới dùng được quyền này");
    }
  };
}
function hideCheckNote(row) {
  clearTimeout(row._noteTimer);
  row.classList.remove("auto");
  row.querySelector(".check-note")?.remove();
}
// Nháy dòng quyền vừa được tự bật kèm chú thích ngắn, để người dùng hiểu vì sao nó được tick
function flashCheck(row, hint) {
  row.classList.remove("auto");
  void row.offsetWidth;
  row.classList.add("auto");
  let note = row.querySelector(".check-note");
  if (!note) row.insertAdjacentHTML("beforeend", `<em class="check-note"></em>`), (note = row.querySelector(".check-note"));
  note.textContent = hint;
  const arm = () => { clearTimeout(row._noteTimer); row._noteTimer = setTimeout(() => hideCheckNote(row), 2600); };
  // Rê chuột vào thì giữ chú thích hiện, thả ra vài giây sau mới ẩn
  row.onmouseenter = () => clearTimeout(row._noteTimer);
  row.onmouseleave = () => { if (row.querySelector(".check-note")) arm(); };
  if (row.matches(":hover")) clearTimeout(row._noteTimer); else arm();
}
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
    Object.assign(state.user, { pending_requests: st.user?.pending_requests || 0, pending_links: st.user?.pending_links || 0,
      pending_accounts: st.user?.pending_accounts || 0, profile_notices: st.user?.profile_notices || 0 });
    setBadges(state.user);
    // có kết quả duyệt mới trong lúc đang dùng app: báo ngay thay vì đợi user tự mở trang
    if (state.user.profile_notices > prev && state.view !== "profile") toast("Quản trị viên vừa xử lý yêu cầu của bạn. Xem ở mục Hồ sơ của tôi.");
  } catch {}
}
function setBadges(u) {
  for (const [id, n] of [["access-badge", u.pending_requests], ["users-badge", (u.pending_links || 0) + (u.pending_accounts || 0)], ["profile-badge", u.profile_notices]]) {
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
  const show = { chat: u.can_use_ai, myfiles: u.can_use_ai, memory: u.can_use_ai, insights: can("insights"), users: ["admin", "ceo"].includes(u.role), access: u.role !== "ceo", docs: can("docs_view"), history: ["admin", "ceo"].includes(u.role), budget: ["admin", "ceo"].includes(u.role), aicost: ["admin", "ceo"].includes(u.role), proposals: u.can_use_ai || u.proposals_assigned > 0 };
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
  if (location.pathname !== "/" || location.hash) { const r = parsePath(); go(r.view, r.extra, true); }
  else go(state.view);
}

function renderLogin(needsSetup, registering = false) {
  clearTimeout(pollTimer);
  $("#userbox").innerHTML = "";
  const showRegister = !needsSetup && registering;
  const title = needsSetup ? "Tạo tài khoản quản trị đầu tiên" : showRegister ? "Đăng ký tài khoản" : "Đăng nhập";
  const lead = needsSetup
    ? "Hệ thống chưa có tài khoản nào. Tài khoản này có toàn quyền và dùng để cấp tài khoản cho người khác."
    : showRegister ? "Điền thông tin để gửi yêu cầu. Quản trị viên sẽ duyệt tài khoản trước khi bạn đăng nhập."
    : "Chào mừng trở lại. Vui lòng đăng nhập để tiếp tục.";
  const switchLink = needsSetup ? "" : showRegister
    ? 'Đã có tài khoản? <button type="button" class="link" data-switch="login">Đăng nhập</button>'
    : 'Chưa có tài khoản? <button type="button" class="link" data-switch="register">Đăng ký</button>';
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
      <h2>${title}</h2>
      <p class="muted" style="margin:0 0 20px">${lead}</p>
      <form id="login-form">
        ${needsSetup ? `<div class="field"><label>Họ tên</label><input name="full_name"></div>` : ""}
        ${showRegister ? `<div class="field"><label>Họ tên</label><input name="full_name" required maxlength="100" autocomplete="name"></div>` : ""}
        <div class="field"><label>Tên đăng nhập</label><input name="username" required autocomplete="username"${showRegister ? ' pattern="[A-Za-z0-9._-]{3,32}" maxlength="32" title="3–32 ký tự: chữ không dấu, số, . _ -"' : ""}>
          ${showRegister ? '<small class="muted">Chữ không dấu, số, . _ - (3–32 ký tự), tự chuyển về chữ thường</small>' : ""}</div>
        <div class="field"><label>Mật khẩu${needsSetup || showRegister ? " (tối thiểu 8 ký tự)" : ""}</label>
          <input name="password" type="password" required autocomplete="${needsSetup || showRegister ? "new-password" : "current-password"}"></div>
        ${showRegister ? `<div class="field"><label>Nhập lại mật khẩu</label><input name="password2" type="password" required autocomplete="new-password"></div>
        <div class="field"><label>Phòng ban / công trình</label>
          <div class="unit-pick"><input name="unit" required maxlength="100" autocomplete="off" placeholder="Gõ để tìm, ví dụ: P. Kế toán">
            <div class="unit-pick-list" hidden></div></div>
          <small class="muted">Chọn từ gợi ý; nếu chưa có trong danh sách thì ghi rõ tên đơn vị</small></div>
        <div class="field"><label>Số máy lẻ nội bộ (không bắt buộc)</label><input name="phone" maxlength="20" inputmode="tel" autocomplete="off" placeholder="VD: 123">
        </div>` : ""}
        <div class="danger" id="login-err"></div>
        <button class="primary" style="width:100%">${needsSetup ? "Tạo tài khoản" : showRegister ? "Gửi yêu cầu đăng ký" : "Đăng nhập"} ${icon("arrow")}</button>
      </form>
      ${switchLink ? `<p class="muted" style="margin:16px 0 0;text-align:center">${switchLink}</p>` : ""}
    </div></div></div>`;
  $("[data-switch]")?.addEventListener("click", (e) => renderLogin(false, e.target.dataset.switch === "register"));
  if (showRegister) {  // gợi ý phòng ban: lọc theo tên viết tắt lẫn đầy đủ, tối đa 8 dòng, không thanh cuộn; lỗi mạng thì vẫn gõ tự do được
    const input = $("#login-form [name=unit]");
    const box = $("#login-form .unit-pick-list");
    let units = [];
    let hits = [];
    let active = -1;
    const paint = () => {
      const typed = input.value.trim();
      const rowsHtml = hits.map((u, i) => `<div class="unit-pick-item${i === active ? " active" : ""}" data-i="${i}"><b>${esc(u.name)}</b>${u.full_name && u.full_name !== u.name ? `<small>${esc(u.full_name)}</small>` : ""}</div>`).join("");
      const foot = typed && !hits.some((u) => u.name === typed) ? `<div class="unit-pick-foot">Không thấy đơn vị của bạn? Cứ giữ nguyên “${esc(typed)}”</div>` : "";
      box.innerHTML = rowsHtml + foot;
      box.hidden = !box.innerHTML;
    };
    const expand = (name) => name.replace(/^P\.\s*/, "Phòng ");  // "P. IT" tìm được bằng "Phòng IT"
    const search = () => {
      const q = input.value;
      const rect = input.getBoundingClientRect();  // chỉ hiện số dòng vừa với khoảng trống, mở lên trên nếu bên dưới chật, để không đẩy bố cục trang
      const below = window.innerHeight - rect.bottom - 16, above = rect.top - 16;
      const up = below < 200 && above > below;
      const limit = Math.max(3, Math.min(8, Math.floor(((up ? above : below) - 50) / 50)));
      box.classList.toggle("up", up);
      hits = units.filter((u) => matchWords(q, `${expand(u.name)} ${u.full_name || ""} ${u.keywords || ""}`)).slice(0, limit);
      active = -1;
      paint();
    };
    const pick = (u) => { input.value = u.name; box.hidden = true; };
    input.addEventListener("focus", search);
    input.addEventListener("input", search);
    input.addEventListener("blur", () => { box.hidden = true; });
    input.addEventListener("keydown", (e) => {
      if (box.hidden || !hits.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const step = e.key === "ArrowDown" ? 1 : -1;
        active = active < 0 ? (step > 0 ? 0 : hits.length - 1) : (active + step + hits.length) % hits.length;
        paint();
      } else if (e.key === "Enter" && active >= 0) {
        e.preventDefault();
        pick(hits[active]);
      } else if (e.key === "Escape") {
        box.hidden = true;
      }
    });
    box.addEventListener("mousedown", (e) => {  // mousedown + preventDefault để ô nhập không mất focus trước khi chọn
      e.preventDefault();
      const item = e.target.closest(".unit-pick-item");
      if (item) pick(hits[Number(item.dataset.i)]);
    });
    fetch("/api/auth/units").then((r) => (r.ok ? r.json() : [])).then((list) => {
      units = list;
      if (document.activeElement === input) search();
    }).catch(() => {});
  }
  $("#login-form").querySelectorAll('input[type="password"]').forEach((inp) => {  // nút Hiện/Ẩn mật khẩu
    const wrap = document.createElement("div");
    wrap.className = "pw-wrap";
    inp.replaceWith(wrap);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "link pw-toggle";
    btn.textContent = "Hiện";
    btn.onclick = () => {
      const show = inp.type === "password";
      inp.type = show ? "text" : "password";
      btn.textContent = show ? "Ẩn" : "Hiện";
    };
    wrap.append(inp, btn);
  });
  $("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target.elements;
    const body = { username: f.username.value, password: f.password.value };
    if (needsSetup || showRegister) body.full_name = f.full_name.value;
    if (showRegister) {
      if (f.password.value !== f.password2.value) { $("#login-err").textContent = "Mật khẩu nhập lại không khớp"; return; }
      body.unit = f.unit.value;
      body.phone = f.phone.value;
      try {
        await api("/api/auth/register", { method: "POST", body });
        $(".auth-form .card").innerHTML = `
          <h2>Đã gửi yêu cầu đăng ký</h2>
          <p class="muted" style="margin:0 0 20px">Tài khoản <b>${esc(body.username)}</b> đang chờ quản trị viên duyệt. Sau khi được duyệt, bạn có thể đăng nhập bằng tên đăng nhập và mật khẩu vừa tạo.</p>
          <button class="primary" style="width:100%" data-switch="login">Quay lại đăng nhập</button>`;
        $("[data-switch]").addEventListener("click", () => renderLogin(false, false));
      } catch (err) {
        $("#login-err").textContent = err.message;
      }
      return;
    }
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
$("#home-logo").onclick = () => go("overview");
$("#menu-btn").onclick =() => document.body.classList.toggle("nav-open");
$("#scrim").onclick = () => document.body.classList.remove("nav-open");
addEventListener("scroll", () => document.body.classList.toggle("scrolled", scrollY > 4), { passive: true });
const can = (feature) => !!state.user?.permissions?.includes(feature);
const canSee = (view) => !document.querySelector(`#nav button[data-view="${view}"]`)?.hidden;

// Đường dẫn tiếng Việt: /phong-ban/<id>/<tab>, /nhan-su/<id>, /muc-tieu-doanh-thu/<id>...; trang chủ (Tổng quan) giữ nguyên "/".
// Đổi trang thì ghi vào lịch sử để Back/F5/chia sẻ link hoạt động. Backend trả index.html cho các đường dẫn này (spa_fallback trong app.py).
const VIEW_SLUG = { overview: "", chart: "so-do-to-chuc", units: "phong-ban", people: "nhan-su", targets: "muc-tieu-doanh-thu", budget: "ngan-sach", proposals: "de-xuat",
  docs: "tai-lieu", insights: "phan-tich", chat: "tro-ly-ai", myfiles: "du-lieu-cua-toi", profile: "ho-so-cua-toi", memory: "ai-nho-gi-ve-toi",
  history: "lich-su-thay-doi", users: "tai-khoan", access: "quyen-truy-cap" };
const TAB_SLUG = { org: "so-do", process: "quy-trinh", docs: "tai-lieu", target: "muc-tieu", info: "chuc-nang" };
const invert = (m) => Object.fromEntries([...Object.entries(m).map(([k, v]) => [v, k]), ...Object.keys(m).map((k) => [k, k])]);  // nhận cả tên tiếng Anh của link cũ
const SLUG_VIEW = invert(VIEW_SLUG), SLUG_TAB = invert(TAB_SLUG);

function buildPath(view, extra = {}) {
  const parts = [VIEW_SLUG[view]];
  if (view === "units" && state.unitId) parts.push(state.unitId, TAB_SLUG[state.unitTab]);
  if (view === "people" && extra.peopleFocus) parts.push(extra.peopleFocus);
  if (view === "targets" && extra.targetFocus) parts.push(extra.targetFocus);
  return "/" + parts.filter((p) => p !== "").join("/");
}
function parsePath() {
  // link cũ dạng /#/units/5/org vẫn mở được
  const src = location.hash.startsWith("#/") ? location.hash.slice(1) : location.pathname;
  const [slug, a, b] = src.replace(/^\/+/, "").split("/");
  const view = slug ? SLUG_VIEW[slug] : "overview";
  if (!view || !VIEWS[view] || !canSee(view)) return { view: "overview", extra: {} };
  const id = Number(a), extra = {};
  if (view === "units") {
    if (id > 0) extra.unitId = id;
    if (SLUG_TAB[b]) extra.unitTab = SLUG_TAB[b];
  }
  if (view === "people" && id > 0) extra.peopleFocus = id;
  if (view === "targets" && id > 0) extra.targetFocus = id;
  return { view, extra };
}
function syncPath(view, extra, replace) {
  const p = buildPath(view, extra);
  if (p === location.pathname && !location.hash) return;
  history[replace ? "replaceState" : "pushState"](null, "", p);
}
addEventListener("popstate", () => {
  if (!state.user) return;
  const r = parsePath();
  go(r.view, r.extra, true);
});

addEventListener("beforeprint", () => { if (state.view === "budget") state.bkPrint?.before(); });  // trang Ngân sách: mở hết nhóm khi in
addEventListener("afterprint", () => { if (state.view === "budget") state.bkPrint?.after(); });

// fromUrl: điều hướng do mở link / Back / Forward, nên chỉ chuẩn hoá URL chứ không thêm mục lịch sử
function go(view, extra = {}, fromUrl = false) {
  const changed = view !== state.view;
  Object.assign(state, { view }, extra);
  syncPath(view, extra, fromUrl);
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
    // trang đơn vị tự chọn đơn vị mặc định khi vẽ: cập nhật đường dẫn mà không thêm mục lịch sử
    if (state.view === "units") syncPath("units", {}, true);
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
// Năm chỉ tiêu trọng yếu nhập cùng lúc: mỗi chỉ tiêu một cặp "mục tiêu / thực hiện"; ô để trống thì bỏ qua.
// Theo "Mục tiêu và chương trình hành động công ty": KRI 01 doanh số, KRI 02 doanh thu, KRI 03 chi phí/hiệu quả tài chính,
// KRI 04 dòng tiền (thu hồi công nợ, thu tiền), KRI 05 OKRs dự án. Tiền nhập theo tỷ đồng, lưu theo VNĐ như dữ liệu cũ.
const KEY_METRICS = ["doanh_so", "doanh_thu", "loi_nhuan", "dong_tien", "okr_du_an"];
const KEY_METRIC_FORM = {
  doanh_so: { unit: "tỷ đồng", hint: "KRI 01" },
  doanh_thu: { unit: "tỷ đồng", hint: "KRI 02" },
  loi_nhuan: { unit: "tỷ đồng", hint: "KRI 03" },
  dong_tien: { unit: "%", hint: "KRI 04 – tỷ lệ thu hồi công nợ, thu tiền" },
  okr_du_an: { unit: "%", hint: "KRI 05 – tỷ lệ dự án đạt yêu cầu" },
};

// Kỳ nhập bằng hai ô Năm + Kỳ (Cả năm / Quý 1–4) rồi ghép thành "2026" hoặc "2026-Q3" như dữ liệu cũ.
const QUARTERS = [["", "Cả năm"], ["Q1", "Quý 1"], ["Q2", "Quý 2"], ["Q3", "Quý 3"], ["Q4", "Quý 4"]];
const periodFields = () => [
  { name: "year", label: "Năm", required: true, placeholder: "2026", half: true },
  { name: "quarter", label: "Kỳ", type: "select", options: QUARTERS, half: true },
];
function periodValues(p) {
  const m = /^(\d{4})(?:-(Q[1-4]))?$/.exec(String(p || ""));
  return { year: m ? m[1] : /^\d{4}/.exec(String(p || ""))?.[0] || String(new Date().getFullYear()), quarter: m?.[2] || "" };
}
function joinPeriod(raw) {
  const y = String(raw.year || "").trim();
  if (!/^\d{4}$/.test(y)) throw new Error("năm gồm 4 chữ số, ví dụ 2026.");
  return raw.quarter ? `${y}-${raw.quarter}` : y;
}

function keyMetricFields() {
  return KEY_METRICS.map((m, i) => ({
    type: "pair", head: i === 0, names: [`${m}_target`, `${m}_actual`], labels: ["Mục tiêu", "Thực hiện"],
    label: METRICS[m], hint: `${KEY_METRIC_FORM[m].unit} · ${KEY_METRIC_FORM[m].hint}`,
  }));
}

// Lưu các chỉ tiêu đã nhập: đã có dòng cùng đơn vị + kỳ + loại thì cập nhật, chưa có thì thêm mới.
async function saveKeyMetrics(raw, unitId, period) {
  period = String(period || "").trim();
  if (!period) throw new Error("cần nhập kỳ.");
  const scale = (m) => (KEY_METRIC_FORM[m].unit === "%" ? 1 : 1e9);  // ô nhập là tỷ đồng → VNĐ
  const num = (m, v) => (v === "" || v == null ? null : Math.round(Number(v) * scale(m) * 100) / 100);
  const filled = KEY_METRICS.filter((m) => num(m, raw[`${m}_target`]) != null || num(m, raw[`${m}_actual`]) != null);
  if (!filled.length) throw new Error("nhập ít nhất một chỉ tiêu (mục tiêu hoặc thực hiện).");
  const existing = await api("/api/targets");
  for (const m of filled) {
    const body = { unit_id: unitId, period, metric: m, metric_name: "", target_value: num(m, raw[`${m}_target`]),
                   actual_value: num(m, raw[`${m}_actual`]), unit_label: KEY_METRIC_FORM[m].unit === "%" ? "%" : "VNĐ" };
    const old = existing.find((t) => (t.unit_id ?? null) === unitId && t.period === period && t.metric === m);
    await api(old ? `/api/targets/${old.id}` : "/api/targets", { method: old ? "PUT" : "POST", body });
  }
}

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
      } else if (f.type === "units") {  // chọn nhiều đơn vị: chip đã chọn + ô tìm để thêm
        input = `<div class="unit-pick" data-units="${f.name}"><div class="unit-chips"></div>
          <input type="search" class="unit-q" placeholder="${esc(f.placeholder || "Gõ tên phòng ban để thêm...")}" autocomplete="off">
          <div class="combo-list" hidden></div></div>`;
      } else if (f.type === "pair") {  // một hàng: tên chỉ tiêu + hai ô số cạnh nhau (mục tiêu / thực hiện)
        const [a, b] = f.names, [la, lb] = f.labels;
        return `${f.head ? `<div class="pair-row pair-head"><span></span><span>${esc(la)}</span><span>${esc(lb)}</span></div>` : ""}
          <div class="pair-row"><div class="pair-name"><b>${esc(f.label)}</b><small>${esc(f.hint || "")}</small></div>
            <input name="${a}" type="number" step="any" value="${esc(values[a] ?? "")}" placeholder="${esc(la)}" aria-label="${esc(f.label)} – ${esc(la)}">
            <input name="${b}" type="number" step="any" value="${esc(values[b] ?? "")}" placeholder="${esc(lb)}" aria-label="${esc(f.label)} – ${esc(lb)}"></div>`;
      } else if (f.type === "info") {
        return f.group ? `<div class="form-group">${esc(f.label)}</div>` : `<p class="muted" style="margin:0 0 8px">${esc(f.label)}</p>`;
      } else if (f.type === "check") {
        return `<label class="check${f.compact ? " compact" : ""}"><input type="checkbox" name="${f.name}" ${v ? "checked" : ""}><span>${esc(f.label)}</span></label>`;
      } else if (f.type === "file") {
        input = `<input name="${f.name}" type="file" accept="${esc(f.accept || "")}" ${f.required ? "required" : ""}>`;
      } else {
        input = `<input name="${f.name}" type="${f.type || "text"}" value="${esc(v)}" placeholder="${esc(f.placeholder || "")}" ${f.required ? "required" : ""} step="any"${f.type === "password" ? ' autocomplete="new-password" readonly onfocus="this.readOnly=false"' : ""}>`;
      }
      return `<div class="field${f.half ? " half" : ""}"><label>${esc(f.label)}</label>${input}</div>`;
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
  const picks = {};  // field.type "units": tên trường -> Set id đơn vị đã chọn
  fields.filter((f) => f.type === "units").forEach((f) => {
    const root = form.querySelector(`[data-units="${f.name}"]`), chips = root.querySelector(".unit-chips");
    const box = root.querySelector(".unit-q"), list = root.querySelector(".combo-list");
    const primary = () => (f.primary && form.elements[f.primary] ? String(form.elements[f.primary].value) : "");
    const sel = (picks[f.name] = new Set((values[f.name] || []).map(String)));
    const nameOf = (id) => (f.options.find(([v]) => String(v) === id) || [, id])[1];
    const drawChips = () => {
      chips.innerHTML = sel.size
        ? [...sel].map((id, i) => `<span class="unit-chip${f.ordered && i === 0 ? " main" : ""}">${f.ordered && i === 0 ? '<em>Chủ quản</em>' : f.ordered ? `<button type="button" class="mk" data-main="${esc(id)}" title="Đặt làm đơn vị chủ quản">☆</button>` : ""}${esc(nameOf(id))}<button type="button" data-rm="${esc(id)}" aria-label="Bỏ ${esc(nameOf(id))}">×</button></span>`).join("")
        : `<span class="muted">${esc(f.empty || "Chưa chia sẻ cho phòng ban nào khác.")}</span>`;
    };
    const show = () => {
      const q = plain(box.value.trim());
      const hits = f.options.filter(([v, l]) => String(v) !== primary() && !sel.has(String(v)) && (!q || plain(l).includes(q)));
      list.innerHTML = hits.length
        ? hits.map(([v, l]) => `<button type="button" class="combo-item" data-val="${esc(v)}">${esc(l)}</button>`).join("")
        : '<div class="combo-empty">Không còn phòng ban nào khớp.</div>';
      list.hidden = false;
    };
    chips.onclick = (e) => {
      const b = e.target.closest("[data-rm]"), m = e.target.closest("[data-main]");
      if (b) sel.delete(b.dataset.rm);
      else if (m) { const rest = [...sel].filter((x) => x !== m.dataset.main); sel.clear(); [m.dataset.main, ...rest].forEach((x) => sel.add(x)); }
      else return;
      drawChips();
    };
    box.oninput = box.onfocus = show;
    box.onkeydown = (e) => {
      if (e.key === "Enter") { e.preventDefault(); list.querySelector(".combo-item")?.click(); }
      else if (e.key === "Escape" && !list.hidden) { e.stopPropagation(); e.preventDefault(); list.hidden = true; }
    };
    list.onmousedown = (e) => e.preventDefault();
    list.onclick = (e) => {
      const b = e.target.closest(".combo-item");
      if (!b) return;
      sel.add(b.dataset.val); box.value = ""; drawChips(); show();
    };
    box.onblur = () => { list.hidden = true; };
    if (f.primary && form.elements[f.primary]) form.elements[f.primary].addEventListener("change", () => { sel.delete(primary()); drawChips(); });
    sel.delete(primary());
    drawChips();
  });
  form.onsubmit = async (e) => {
    e.preventDefault();
    const data = {};
    fields.forEach((f) => {
      if (f.type === "units") return (data[f.name] = [...picks[f.name]].map(Number));
      if (f.type === "file") return (data[f.name] = form.elements[f.name].files[0]);
      if (f.type === "info") return;
      if (f.type === "pair") return f.names.forEach((n) => { const v = form.elements[n].value; data[n] = v === "" ? null : Number(v); });
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
  // form dài: chỉ phần nội dung cuộn, thanh Hủy/Lưu luôn nằm trong màn hình
  modal.classList.add("fit");
  modal.addEventListener("close", () => modal.classList.remove("fit"), { once: true });
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
                <span class="track"><span class="fill" data-w="${(n / maxDiv) * 100}"></span></span><b class="v">${fmtNum(n)}</b></div>`).join("")}</div>
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
              <span class="track"><span class="fill" data-w="${(n / maxDiv) * 100}"></span></span><b class="v">${fmtNum(n)}</b></div>`).join("")}</div>
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
    // Thứ tự các nhánh dưới TGĐ theo sơ đồ gốc REV02
    const COL_ORDER = ["K-NSHC", "K-VH", "PTGD-TC", "PTGD-TT", "PTGD-TM"];
    const colRank = (c) => { const i = COL_ORDER.indexOf(c.code); return i < 0 ? 99 : i; };
    const cols = tgd.children.filter((c) => c !== troly && c !== bqlda).sort((a, b) => colRank(a) - colRank(b));

    const headTxt = (u) => (u.head ? `${esc(u.head.title_code)}. ${esc(u.head.name)}` : "");
    const bar = (u, bg, note = "") =>
      `<div class="org-bar" style="background:${bg}" onclick="go('units',{unitId:${u.id}})">
         <div class="t">${esc(u.name)}</div><div>${headTxt(u)}</div>${note ? `<div class="note">${note}</div>` : ""}</div>`;
    // Trưởng ban KSNB kiêm chức vụ khác dưới TGĐ (VD PTGĐ Tài chính) -> ghi chú để không hiểu nhầm là cấp trên TGĐ
    const ksnbAlso = ksnb.head && tgd.children.find((c) => c.head && c.head.name === ksnb.head.name && c.unit_type === "executive");
    const ksnbNote = ksnbAlso ? `kiêm ${esc(ksnbAlso.name)}` : "";
    const nodeSelf = (u, top = false) => `
      <div class="org-node ${top ? "top" : ""} ${u.head && u.head.name === "TBA" ? "tba" : ""}"
           style="--c:${color(u.color_group)}; --ct:${u.color_group === "commercial" ? "#3d2b00" : "#fff"}"
           onclick="event.stopPropagation(); go('units',{unitId:${u.id}})">
        <div class="n">${esc(u.name)} ${u.verified ? "" : '<span class="badge warn" title="Cần xác nhận">?</span>'}</div>
        <div class="h">${headTxt(u) || "—"}</div>
        ${(u.deputies || []).map((d) => `<div class="h">${esc(d.title_code)}. ${esc(d.name)}</div>`).join("")}
      </div>`;
    const HIDDEN_IN_CHART = ["DV-HCNS"];  // Bộ phận Dịch vụ: ẩn khỏi sơ đồ, vẫn có trong danh sách đơn vị
    const shown = (u) => u.children.filter((c) => !HIDDEN_IN_CHART.includes(c.code));
    const node = (u) => nodeSelf(u) + (shown(u).length ? `<div class="org-children">${shown(u).map(node).join("")}</div>` : "");
    // Cột cấp 1 (PTGĐ / Khối): nếu có ≥2 khối con thì xếp ngang như sơ đồ gốc (VD PTGĐ Thường trực: Kinh tế KT | Thi công | QA/QC, HSSE)
    const splitOf = (u) => {
      const divs = u.children.filter((c) => c.unit_type === "division");
      return divs.length >= 2 ? { divs, rest: u.children.filter((c) => c.unit_type !== "division") } : null;
    };
    const colBody = (u) => {
      const sp = splitOf(u);
      if (sp) return `<div class="org-split">${sp.divs.map((d) => `<div>${node(d)}</div>`).join("")}${sp.rest.length ? `<div>${sp.rest.map(node).join("")}</div>` : ""}</div>`;
      return shown(u).length ? `<div class="org-children">${shown(u).map(node).join("")}</div>` : "";
    };
    const colWeight = (u) => { const sp = splitOf(u); return sp ? (sp.divs.length + (sp.rest.length ? 1 : 0)) * 1.15 : 1; };
    const ptgdTT = cols.find((c) => c.code === "PTGD-TT");

    main.innerHTML = `
      <div class="page-head"><div><h2>Sơ đồ điều hành</h2><p>AZB-SDTC-REV02 · hiệu lực 01/08/2026</p></div></div>
      <div class="legend">${Object.entries(COLOR_GROUPS).map(([k, v]) => `<span><i style="background:${color(k)}"></i>${v}</span>`).join("")}
        <span><span class="badge warn">?</span> cần xác nhận</span></div>
      <div class="org-scroll"><div class="org-inner">
        <div class="org-row">${bar(hdqt, "var(--org-warm)")}</div>
        <div class="org-row org-side org-audit">${bar(ksnb, "var(--org-warm)", ksnbNote)}</div>
        <div class="org-row">${bar(tgd, "var(--org-green)")}</div>
        <div class="org-row org-side org-assist">${bar(troly, "var(--org-green)")}</div>
        <div class="org-cols" style="grid-template-columns:${cols.map((c) => `minmax(0,${colWeight(c)}fr)`).join(" ")}">
          ${cols.map((c) => `<div class="org-col">${nodeSelf(c, true)}${colBody(c)}</div>`).join("")}</div>
        <div class="org-row" style="margin-top:14px">${bar(bqlda, "var(--org-warm)")}</div>
      </div></div>
      <p class="muted">Bấm vào ô bất kỳ để xem chi tiết đơn vị. Tất cả phòng ban hỗ trợ các Ban Quản lý Dự án.
        ${ptgdTT && ptgdTT.notes ? `<br><b>Ghi chú:</b> ${esc(ptgdTT.notes)}` : ""}</p>`;
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
    const all = await api("/api/employees");
    // Mở từ liên kết (tên người tải lên...): hiện đúng người đó, kể cả khi họ đã nghỉ việc đang bị ẩn
    const reveal = state.peopleReveal ? state.peopleFocus : null;
    state.peopleReveal = false;
    if (reveal && all.some((e) => e.id === reveal && e.status === "inactive")) state.showInactive = true;
    const emps = all.filter((e) => state.showInactive || e.status !== "inactive");
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
    if (reveal && !state.peopleQuery.trim()) {
      const target = emps.find((e) => e.id === reveal);
      if (target) {
        state.openDepts.add(target.hr_department || "Chưa có trong danh sách HCNS");  // mở đúng phòng ban chứa người đó
        drawList();
        const tr = listEl.querySelector(`tr[data-emp="${reveal}"]`);
        if (tr) {
          tr.scrollIntoView({ block: "center", behavior: "smooth" });
          tr.classList.add("flash");
        }
      }
    }

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

  async history(main) {
    const PAGE = 50;
    const ACT = { create: "Thêm mới", update: "Sửa", delete: "Xoá" };
    const ACT_CLASS = { create: "ok", update: "brand", delete: "bad" };
    const TBL = { units: "Đơn vị", employees: "Nhân sự", positions: "Chức danh", processes: "Quy trình", targets: "Mục tiêu" };
    const h = (state.hist ||= { entity: "", action: "", user_id: "", q: "", date_from: "", date_to: "", page: 0, open: new Set() });
    const params = (extra = {}) => {
      const p = new URLSearchParams();
      for (const k of ["entity", "action", "user_id", "q", "date_from", "date_to"]) if (h[k]) p.set(k, h[k]);
      for (const [k, v] of Object.entries(extra)) p.set(k, v);
      return p.toString();
    };
    const data = await api(`/api/change-history/page?${params({ limit: PAGE, offset: h.page * PAGE })}`);
    const pages = Math.max(1, Math.ceil(data.total / PAGE));
    if (h.page >= pages) { h.page = pages - 1; return VIEWS.history(main); }

    const money = (n) => {  // tiền rút gọn: 50 tỷ, 40 triệu
      const v = Number(n), a = Math.abs(v);
      if (!Number.isFinite(v) || a < 1e6) return fmtNum(n);
      const [d, u] = a >= 1e9 ? [1e9, "tỷ"] : [1e6, "triệu"];
      return `${(v / d).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} ${u}`;
    };
    const val = (field, v) => {
      if (v == null || v === "") return "—";
      if (field === "(đã ẩn)" || v === "(đã ẩn)") return `<span class="muted">(đã ẩn)</span>`;
      if (field === "unit_id" || field === "parent_id") return esc(data.refs.units[v] || `#${v}`);
      if (field === "employee_id") return esc(data.refs.employees[v] || `#${v}`);
      if (field === "target_value" || field === "actual_value") return esc(money(v));
      if (field === "verified" || field === "is_head") return Number(v) ? "Có" : "Không";
      return esc(String(v));
    };
    const diff = (l) => (l.changes && Object.keys(l.changes).length
      ? Object.entries(l.changes).map(([k, [a, b]]) => `<div><span class="muted">${esc(data.fields[k] || k)}:</span> ${val(k, a)} → <b>${val(k, b)}</b></div>`).join("")
      : l.changes ? '<span class="muted">Không có thay đổi giá trị</span>' : esc(l.note || ""));
    const objName = (l) => l.name ? esc(l.name) : l.action === "delete" ? `#${l.entity_id} <span class="muted">(đã xoá, không rõ tên)</span>` : `#${l.entity_id}`;
    const who = (l) => esc(l.user_name || l.username || "—");
    const link = (l) => {
      if (l.action === "delete" || l.undone) return "";
      const to = { units: `go('units',{unitId:${l.entity_id},unitTab:'org'})`, employees: `go('people',{peopleFocus:${l.entity_id}})`, targets: `go('targets',{targetFocus:${l.entity_id}})` }[l.entity];
      return to ? `<button class="link" onclick="${to}">Mở đối tượng →</button>` : "";
    };
    const row = (l, extraClass = "") => `<tr class="hist-row ${extraClass}" data-id="${l.id}" style="cursor:pointer">
        <td class="muted" style="white-space:nowrap">${esc(l.ts)}</td>
        <td>${who(l)}</td>
        <td><span class="badge ${ACT_CLASS[l.action] || ""}">${ACT[l.action] || esc(l.action)}</span>${l.undone ? ' <span class="badge">Đã hoàn tác</span>' : ""}</td>
        <td>${esc(TBL[l.entity] || l.entity)}: <b>${objName(l)}</b></td>
        <td>${diff(l)}</td></tr>
      ${h.open.has(l.id) ? `<tr class="hist-detail"><td colspan="5">
        <div class="toolbar" style="margin:0"><div><b>${objName(l)}</b> · ${esc(TBL[l.entity] || l.entity)} · ${ACT[l.action] || ""} bởi ${who(l)} lúc ${esc(l.ts)}</div>
          <div class="btn-group">${link(l)} ${l.can_undo ? `<button class="ghost" data-undo="${l.id}">${icon("reset")}Hoàn tác</button>` : ""}</div></div>
        <div style="margin-top:8px">${diff(l)}</div></td></tr>` : ""}`;
    // Nhóm các thao tác cùng loại, cùng người, liên tiếp trong 2 phút (xoá hàng loạt...) thành một dòng
    const items = data.items, parts = [];
    for (let i = 0; i < items.length;) {
      let j = i + 1;
      const sameRun = (a, b) => a.user_id === b.user_id && a.action === b.action && a.entity === b.entity
        && Math.abs(new Date(a.ts.replace(" ", "T")) - new Date(b.ts.replace(" ", "T"))) <= 120000;
      while (j < items.length && sameRun(items[i], items[j])) j++;
      parts.push(items.slice(i, j));
      i = j;
    }
    const body = parts.map((g) => {
      if (g.length < 3) return g.map((l) => row(l)).join("");
      const key = `g${g[0].id}`, open = h.open.has(key), l0 = g[0];
      return `<tr class="hist-group" data-group="${key}" style="cursor:pointer"><td class="muted" style="white-space:nowrap">${esc(l0.ts.slice(0, 10))} ${esc(g[g.length - 1].ts.slice(11))} – ${esc(l0.ts.slice(11))}</td>
        <td>${who(l0)}</td><td><span class="badge ${ACT_CLASS[l0.action] || ""}">${ACT[l0.action]}</span></td>
        <td colspan="2"><b>${g.length} ${esc((TBL[l0.entity] || l0.entity).toLowerCase())}</b> <span class="muted">${open ? "▾ thu gọn" : "▸ bấm để xem từng mục"}</span></td></tr>
        ${open ? g.map((l) => row(l, "hist-child")).join("") : ""}`;
    }).join("");

    const sel = (name, opts, label) => `<select data-f="${name}" aria-label="${label}"><option value="">${label}</option>
      ${opts.map(([v, t]) => `<option value="${esc(v)}" ${String(h[name]) === String(v) ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
    main.innerHTML = `
      <div class="page-head"><div><h2>Lịch sử thay đổi</h2>
        <p>Ai đã thêm, sửa, xoá gì trong sơ đồ, nhân sự, quy trình và mục tiêu. Thông tin cá nhân (SĐT, email, ngày sinh...) chỉ ghi tên trường, không ghi giá trị. Nếu thao tác nhầm hãy dùng "Hoàn tác" (có trong 90 ngày); nhật ký quá 2 năm được lưu ra file Excel rồi mới dọn khỏi hệ thống.</p></div>
        ${state.user?.role === "admin" ? `<div class="head-actions"><button type="button" class="ghost" id="h-cleanup">${icon("trash")}Dọn nhật ký cũ</button></div>` : ""}</div>
      <div class="card hist-filters">
        <div class="hf-field hf-search"><span>Tìm kiếm</span>
          <div class="hf-input">${icon("search")}<input id="h-q" placeholder="Tìm theo tên đối tượng..." value="${esc(h.q)}"></div></div>
        <div class="hf-field"><span>Đối tượng</span>${sel("entity", Object.entries(TBL), "Mọi đối tượng")}</div>
        <div class="hf-field"><span>Thao tác</span>${sel("action", Object.entries(ACT), "Mọi thao tác")}</div>
        <div class="hf-field"><span>Người thực hiện</span>${sel("user_id", data.users.map((u) => [u.id, u.name]), "Mọi người")}</div>
        <div class="hf-field"><span>Từ ngày</span><input type="date" data-f="date_from" value="${esc(h.date_from)}"></div>
        <div class="hf-field"><span>Đến ngày</span><input type="date" data-f="date_to" value="${esc(h.date_to)}"></div>
        <div class="hf-actions">
          <button class="ghost" id="h-reset">${icon("reset")}Xoá lọc</button>
          <a class="primary btn-link" href="/api/change-history/export?${params()}" download>${icon("download")}Xuất Excel</a>
        </div>
      </div>
      ${items.length ? `<div class="card hist-table"><table>
        <tr><th>Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th>Đối tượng</th><th>Thay đổi</th></tr>${body}</table></div>
        <div class="toolbar" style="margin-top:12px"><span class="muted">${data.total} thay đổi · trang ${h.page + 1}/${pages}</span>
          <div class="btn-group"><button class="ghost" id="h-prev" ${h.page === 0 ? "disabled" : ""}>${icon("left")}Trước</button>
          <button class="ghost" id="h-next" ${h.page + 1 >= pages ? "disabled" : ""}>Sau${icon("right")}</button></div></div>`
        : `<div class="card empty">${h.q || h.entity || h.action || h.user_id || h.date_from || h.date_to ? "Không có thay đổi nào khớp bộ lọc." : "Chưa có thay đổi nào được ghi lại."}</div>`}`;

    const reload = () => VIEWS.history(main).then(() => hydrateIcons(main));
    main.querySelectorAll("[data-f]").forEach((el) => (el.onchange = () => { h[el.dataset.f] = el.value; h.page = 0; reload(); }));
    let timer;
    $("#h-q").oninput = (e) => { clearTimeout(timer); timer = setTimeout(() => { h.q = e.target.value; h.page = 0; reload().then(() => { const q = $("#h-q"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }); }, 350); };
    $("#h-reset").onclick = () => { Object.assign(h, { entity: "", action: "", user_id: "", q: "", date_from: "", date_to: "", page: 0 }); reload(); };
    $("#h-cleanup")?.addEventListener("click", async () => {
      try {
        const p = await api("/api/change-history/cleanup-preview");
        const mb = (n) => (n / 1048576).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
        if (!p.snapshots_to_drop && !p.rows_to_archive) { toast(`Chưa có gì cần dọn (nhật ký hiện ${p.total} dòng, cũ nhất ${p.oldest ? p.oldest.slice(0, 10) : "—"}).`); return; }
        const msg = `Quá ${p.snapshot_days} ngày: bỏ ảnh chụp dùng để Hoàn tác của ${p.snapshots_to_drop} dòng (khoảng ${mb(p.snapshot_bytes)} MB). Các dòng vẫn xem và xuất được.
`
          + `Quá ${p.archive_days} ngày: ${p.rows_to_archive} dòng được lưu ra file Excel trong thư mục archive cạnh database, rồi xoá khỏi hệ thống.`;
        if (!(await confirmBox("Dọn nhật ký cũ?", msg, { okText: "Dọn" }))) return;
        const r = await api("/api/change-history/cleanup", { method: "POST", body: { snapshot_days: p.snapshot_days, archive_days: p.archive_days } });
        toast(`Đã bỏ ${r.snapshots_dropped} ảnh chụp, lưu trữ ${r.rows_archived} dòng${r.archive_file ? ` (${r.archive_file})` : ""}`);
        reload();
      } catch (err) { toast(err.message, "err"); }
    });
    $("#h-prev")?.addEventListener("click", () => { h.page--; reload(); });
    $("#h-next")?.addEventListener("click", () => { h.page++; reload(); });
    const toggle = (key) => { h.open.has(key) ? h.open.delete(key) : h.open.add(key); reload(); };
    main.querySelectorAll(".hist-row").forEach((tr) => (tr.onclick = (e) => { if (!e.target.closest("button,a")) toggle(+tr.dataset.id); }));
    main.querySelectorAll(".hist-group").forEach((tr) => (tr.onclick = () => toggle(tr.dataset.group)));
    main.querySelectorAll("[data-undo]").forEach((b) => (b.onclick = async () => {
      if (!(await confirmBox("Hoàn tác thay đổi?", "Dữ liệu sẽ được đưa về như trước thay đổi này. Việc hoàn tác cũng được ghi vào lịch sử.", { okText: "Hoàn tác" }))) return;
      try { await api(`/api/change-history/${b.dataset.undo}/undo`, { method: "POST" }); toast("Đã hoàn tác"); reload(); }
      catch (err) { toast(err.message, "err"); }
    }));
  },

  async proposals(main) {
    const P = (state.prop ||= { filter: "", open: null });
    if (!P.meta) P.meta = await api("/api/proposals/meta");
    const meta = P.meta, isBoss = !!state.user.edit_all;
    const go = (patch) => { Object.assign(P, patch); VIEWS.proposals(main); };
    const when = (s) => esc(String(s || "").slice(0, 16));
    const prioBadge = (p) => (p.priority === "high" ? '<span class="badge bad">Ưu tiên cao</span>' : p.priority === "low" ? '<span class="badge">Ưu tiên thấp</span>' : "");
    const dueChip = (p) => (p.due_date ? `<span class="pp-chip${p.overdue ? " bad" : ""}">${icon("alert")}Hạn ${esc(p.due_date)}${p.overdue ? " · quá hạn" : ""}</span>` : "");
    // Nhãn nút theo trạng thái hiện tại → trạng thái đích; thứ tự ưu tiên chọn nút chính
    const moveLabel = (from, to) => ({ approved: "Duyệt đề xuất", in_progress: from === "approved" ? "Bắt đầu thực hiện" : from === "review" ? "Trả lại làm tiếp" : "Mở lại thực hiện",
      review: "Báo hoàn thành", done: "Nghiệm thu hoàn thành", dropped: "Không thực hiện", new: "Mở lại đề xuất" })[to];
    const MAIN_ORDER = ["done", "review", "approved", "in_progress", "new"];
    const STEPS = ["new", "approved", "in_progress", "review", "done"];

    if (P.open) {  // ---- Chi tiết một đề xuất ----
      let p;
      try { p = await api(`/api/proposals/${P.open}`); } catch (e) { toast(e.message, "err"); return go({ open: null }); }
      const refresh = () => VIEWS.proposals(main);
      const mine = p.owner_user_id === state.user.id;
      const canResult = isBoss || mine;
      const cur = STEPS.indexOf(p.status);

      const stepper = p.status === "dropped"
        ? `<div class="pp-dropped">${icon("alert")}<span><b>Không thực hiện.</b> ${esc([...p.events].reverse().find((e) => e.to_status === "dropped")?.note || "")}</span></div>`
        : `<ol class="pp-steps">${STEPS.map((s, i) => `<li class="${i < cur || p.status === "done" ? "done" : i === cur ? "now" : ""}"><span class="dot">${i < cur || p.status === "done" ? icon("check") : i + 1}</span><span class="lbl">${PROPOSAL_STATUS[s]}</span></li>`).join("")}</ol>`;

      const moves = [...p.moves].sort((a, b) => MAIN_ORDER.indexOf(a) - MAIN_ORDER.indexOf(b) || 0);
      const mainMove = moves.find((s) => s !== "dropped");
      const btn = (s) => `<button class="${s === mainMove ? "primary" : s === "dropped" ? "ghost danger" : "ghost"}" data-move="${s}">${s === mainMove ? icon("check") : ""}${moveLabel(p.status, s)}</button>`;
      const actions = `${moves.filter((s) => s !== "dropped").map(btn).join("")}${p.can_assign ? `<button class="ghost" id="prop-assign">${icon("users")}Giao việc / đặt hạn</button>` : ""}${moves.includes("dropped") ? btn("dropped") : ""}`;

      const fileCard = (kind, title, hint, canUp) => {
        const fs = p.files.filter((f) => f.kind === kind);
        return `<section class="card pp-card"><div class="pp-card-head"><div><h3>${title}</h3><small>${hint}</small></div>
          ${canUp ? `<button class="ghost pp-sm" data-up="${kind}">${icon("upload")}Tải lên</button>` : ""}</div>
          ${fs.length ? `<ul class="pp-files">${fs.map((f) => `<li><span class="pp-fico">${icon("file")}</span>
            <div class="pp-fmeta"><a href="/api/proposals/${p.id}/files/${f.id}">${esc(f.filename)}</a>
              <small>${fmtSize(f.size_bytes)} · ${esc(f.by_name || "—")} · ${when(f.uploaded_at)}</small></div>
            ${isBoss || f.uploaded_by === state.user.id ? `<button class="link danger" data-del-file="${f.id}">Xoá</button>` : ""}</li>`).join("")}</ul>`
            : `<div class="pp-empty">Chưa có file${canUp ? ' — bấm “Tải lên” để thêm' : ""}.</div>`}</section>`;
      };

      const EV = { create: "Tạo đề xuất", assign: "Giao việc", note: "Cập nhật ghi chú", file: "File" };
      const events = [...p.events].reverse().map((e) => `<li class="${e.kind}"><span class="pp-dot"></span><div>
        <b>${e.kind === "status" ? `${esc(PROPOSAL_STATUS[e.from_status] || "")} → ${esc(PROPOSAL_STATUS[e.to_status] || "")}` : esc(EV[e.kind] || e.kind)}</b>
        ${e.note ? `<p>${esc(e.note)}</p>` : ""}<small>${esc(e.by_name || "—")} · ${when(e.at)}</small></div></li>`).join("");

      main.innerHTML = `
        <button class="link pp-back" id="prop-back">← Danh sách đề xuất</button>
        <section class="card pp-head">
          <div class="pp-title"><h2>${esc(p.title)}</h2><span class="badge ${PROPOSAL_CLASS[p.status]}">${PROPOSAL_STATUS[p.status]}</span></div>
          <div class="pp-chips"><span class="pp-chip">${icon("users")}${esc(p.author || "—")}</span><span class="pp-chip">${when(p.created_at)}</span>${dueChip(p)}${prioBadge(p)}</div>
          ${stepper}
          <div class="pp-actions">${actions || '<span class="muted">Bạn chỉ xem được đề xuất này.</span>'}</div>
        </section>
        <div class="pp-grid">
          <div class="pp-col">
            ${p.body ? `<section class="card pp-card"><div class="pp-card-head"><div><h3>Nội dung đề xuất</h3></div></div><div class="pp-body">${esc(p.body)}</div></section>` : ""}
            ${fileCard("ref", "Tài liệu tham chiếu", "Tài liệu liên quan để người thực hiện đối chiếu", true)}
            ${fileCard("result", "Kết quả / bằng chứng thực hiện", "Bắt buộc có ít nhất một file trước khi báo hoàn thành", canResult)}
          </div>
          <aside class="pp-col">
            <section class="card pp-card"><div class="pp-card-head"><div><h3>Thông tin xử lý</h3></div></div>
              <dl class="pp-info"><dt>Người phụ trách</dt><dd>${p.owner_name || p.owner ? esc(p.owner_name || p.owner) : '<span class="muted">Chưa giao</span>'}</dd>
                <dt>Hạn hoàn thành</dt><dd>${p.due_date ? esc(p.due_date) : '<span class="muted">Chưa đặt</span>'}</dd>
                <dt>Ưu tiên</dt><dd>${esc(meta.priority[p.priority] || "Thường")}</dd>
                <dt>Cập nhật gần nhất</dt><dd>${when(p.updated_at)}</dd></dl>
              ${p.note ? `<div class="pp-note"><b>Ghi chú của Ban TGĐ</b><p>${esc(p.note)}</p></div>` : ""}</section>
            <section class="card pp-card"><div class="pp-card-head"><div><h3>Lịch sử tiến trình</h3></div></div><ul class="pp-timeline">${events}</ul></section>
          </aside>
        </div>`;
      $("#prop-back").onclick = () => go({ open: null });
      main.querySelectorAll("[data-move]").forEach((b) => (b.onclick = () => {
        const to = b.dataset.move, label = moveLabel(p.status, to);
        const send = (note) => api(`/api/proposals/${p.id}`, { method: "PUT", body: { status: to, status_note: note || "" } }).then(refresh);
        if (!["dropped", "review", "done"].includes(to)) return send("").catch((e) => toast(e.message, "err"));
        openForm(label, [{ name: "note", label: to === "dropped" ? "Lý do không thực hiện (bắt buộc)" : "Ghi chú (không bắt buộc)", type: "textarea", required: to === "dropped" }],
          {}, (d) => send(d.note), "Xác nhận");
      }));
      $("#prop-assign")?.addEventListener("click", () => openForm("Giao việc / đặt hạn", [
        { name: "owner_user_id", label: "Người phụ trách", type: "select", search: true, numeric: true,
          options: [["", "— Chọn —"], ...meta.assignees.map((u) => [u.id, `${u.full_name || u.username} (${u.username})`])] },
        { name: "due_date", label: "Hạn hoàn thành", type: "date", half: true },
        { name: "priority", label: "Ưu tiên", type: "select", options: Object.entries(meta.priority), half: true },
        { name: "note", label: "Ghi chú của Ban TGĐ", type: "textarea" },
      ], p, (d) => api(`/api/proposals/${p.id}`, { method: "PUT", body: { ...d, owner_user_id: d.owner_user_id || null } }).then(refresh)));
      main.querySelectorAll("[data-up]").forEach((b) => (b.onclick = () => openForm(
        b.dataset.up === "ref" ? "Tải tài liệu tham chiếu" : "Tải file kết quả / bằng chứng",
        [{ name: "file", label: `Chọn file (tối đa ${meta.max_mb} MB)`, type: "file", accept: meta.allowed_ext.join(","), required: true }], {},
        (d) => { const fd = new FormData(); fd.append("kind", b.dataset.up); fd.append("file", d.file); return api(`/api/proposals/${p.id}/files`, { method: "POST", body: fd }).then(refresh); }, "Tải lên")));
      main.querySelectorAll("[data-del-file]").forEach((b) => (b.onclick = async () => {
        if (!(await confirmBox("Xoá file?", "File được chuyển vào thùng rác, không xoá hẳn.", { okText: "Xoá" }))) return;
        try { await api(`/api/proposals/${p.id}/files/${b.dataset.delFile}`, { method: "DELETE" }); refresh(); } catch (e) { toast(e.message, "err"); }
      }));
      return;
    }

    // ---- Danh sách ----
    const q = P.filter === "mine" ? "?mine=true" : P.filter ? `?status=${encodeURIComponent(P.filter)}` : "";
    const list = await api("/api/proposals" + q);
    const tabs = [["", "Tất cả"], ["mine", "Giao cho tôi"], ...Object.entries(PROPOSAL_STATUS)];
    main.innerHTML = `
      <div class="page-head"><div><h2>Đề xuất cải tiến</h2>
        <p>Đề xuất lưu từ câu trả lời của Trợ lý AI. ${isBoss ? "Ban TGĐ duyệt, giao người phụ trách, đặt hạn và nghiệm thu." : "Bạn thấy đề xuất do mình lưu và việc được giao cho mình."}</p></div></div>
      <div class="tabs">${tabs.map(([v, l]) => `<button class="${v === P.filter ? "active" : ""}" data-st="${v}">${l}</button>`).join("")}</div>
      ${list.length ? `<div class="pp-list">${list.map((p) => `<article class="card pp-item" data-open="${p.id}" tabindex="0" role="button">
          <div class="pp-item-main"><h3>${esc(p.title)}</h3>
            <div class="pp-chips"><span class="pp-chip">${icon("users")}${esc(p.author || "—")}</span><span class="pp-chip">${esc(String(p.created_at).slice(0, 10))}</span>
              ${p.owner_name || p.owner ? `<span class="pp-chip brand">Phụ trách: ${esc(p.owner_name || p.owner)}</span>` : ""}${dueChip(p)}${prioBadge(p)}
              ${p.file_count ? `<span class="pp-chip">${icon("file")}${p.file_count} file</span>` : ""}</div></div>
          <span class="badge ${PROPOSAL_CLASS[p.status]}">${PROPOSAL_STATUS[p.status]}</span></article>`).join("")}</div>`
        : '<div class="card empty">Chưa có đề xuất nào. Bấm “Lưu thành đề xuất” dưới câu trả lời của Trợ lý AI để thêm.</div>'}`;
    main.querySelectorAll("[data-st]").forEach((b) => (b.onclick = () => go({ filter: b.dataset.st })));
    main.querySelectorAll("[data-open]").forEach((el) => {
      el.onclick = () => go({ open: el.dataset.open });
      el.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); el.click(); } };
    });
  },

  async targets(main, period) {
    const fetchPeriod = (p) => api("/api/targets/progress" + (p ? `?period=${encodeURIComponent(p)}` : ""));
    let data = await fetchPeriod(period);
    // Mở từ Lịch sử thay đổi: tìm đúng kỳ chứa mục tiêu đó rồi mở sẵn chi tiết dòng
    const focusId = state.targetFocus;
    state.targetFocus = null;
    if (focusId && !data.items.some((t) => t.id === focusId)) {
      for (const p of data.periods.filter((p) => p !== data.period)) {
        const d = await fetchPeriod(p);
        if (d.items.some((t) => t.id === focusId)) { data = d; break; }
      }
    }
    const { periods, period: cur, items, summary, elapsed_pct: elapsed } = data;
    // Chỉ admin/CEO sửa, xoá, thêm mục tiêu ngay trên trang này (dòng toàn công ty không có tab đơn vị để sửa)
    const canEdit = ["admin", "ceo"].includes(state.user?.role);
    const unitOptions = canEdit ? [["", "Toàn công ty"], ...(await api("/api/units")).map((u) => [u.id, u.name])] : [];
    const allTargets = await api("/api/targets");  // đã lọc theo quyền xem; dùng cho bảng theo quý
    const reload = () => VIEWS.targets(main, cur);
    const targetForm = (t = {}) => t.id ? editTargetForm(t) : openForm("Thêm mục tiêu", [
      { name: "unit_id", label: "Đơn vị", type: "select", options: unitOptions },
      ...periodFields(),
      ...keyMetricFields(),
    ], { unit_id: "", ...periodValues(cur) }, async (raw) => {
      await saveKeyMetrics(raw, raw.unit_id ? Number(raw.unit_id) : null, joinPeriod(raw));
      reload();
    });
    const editTargetForm = (t) => openForm("Sửa mục tiêu", [
      { name: "unit_id", label: "Đơn vị", type: "select", options: unitOptions },
      { name: "period", label: "Kỳ", required: true, placeholder: "2026, 2026-Q4 hoặc 2026-10" },
      { name: "metric", label: "Loại chỉ tiêu", type: "select", options: Object.entries(METRICS), default: "doanh_thu" },
      { name: "metric_name", label: "Tên chỉ tiêu (nếu là chỉ tiêu khác)" },
      { name: "target_value", label: "Giá trị mục tiêu", type: "number" },
      { name: "actual_value", label: "Giá trị thực hiện", type: "number" },
      { name: "unit_label", label: "Đơn vị tính", default: "VNĐ" },
      { name: "notes", label: "Ghi chú", type: "textarea" },
    ], { unit_id: "", period: cur, ...t }, async (raw) => {
      if (raw.metric === "khac" && !String(raw.metric_name || "").trim()) throw new Error("loại “Chỉ tiêu khác” cần có tên chỉ tiêu.");
      const body = { ...raw, unit_id: raw.unit_id || null, metric_name: raw.metric === "khac" ? String(raw.metric_name).trim() : "" };
      await api(t.id ? `/api/targets/${t.id}` : "/api/targets", { method: t.id ? "PUT" : "POST", body });
      reload();
    });
    const STATUS ={ behind: ["bad", "Chậm"], watch: ["warn", "Cần theo dõi"], ok: ["ok", "Đạt"], no_data: ["", "Chưa có số"] };
    const tiles = [["ok", "Đạt"], ["watch", "Cần theo dõi"], ["behind", "Chậm"], ["no_data", "Chưa có số"]];
    // Cùng một đơn vị tính thì ghi một lần ở tiêu đề cột; tiền VNĐ rút gọn thành tỷ/triệu.
    const labels = [...new Set(items.map((t) => t.unit_label || ""))];
    const uLabel = labels.length === 1 ? labels[0] : "";
    const fmtMoney = (n, label = uLabel) => {
      if (n == null) return "—";
      const v = Number(n), a = Math.abs(v);
      if (!(label === "" || /vn[dđ]/i.test(label)) || a < 1e6) return fmtNum(v);
      const [d, u] = a >= 1e9 ? [1e9, "tỷ"] : [1e6, "triệu"];
      return `${(v / d).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} ${u}`;
    };
    const gapCell = (t) => (t.target_value == null || t.actual_value == null ? '<span class="muted">—</span>'
      : t.actual_value >= t.target_value ? '<span class="muted">Đã đạt</span>' : fmtMoney(t.target_value - t.actual_value));
    const forecastCell = (t) => (t.forecast_pct == null ? '<span class="muted">—</span>'
      : `${fmtMoney(t.forecast_value)}<br><small class="${t.forecast_pct >= 100 ? "fc-ok" : "fc-low"}">${t.forecast_pct}% mục tiêu</small>`);
    const metricName = (t) => (t.metric === "khac" && t.metric_name ? t.metric_name : METRICS[t.metric] || t.metric);
    // Cộng gộp theo từng chỉ tiêu (cùng loại và đơn vị tính); nhóm nào có dòng thiếu số thì bỏ qua.
    // Chỉ tiêu "khác" có tên dạng "Ngân sách chi phí 2026 — P. Vật tư": phần sau dấu gạch ngang là tên đơn vị, bỏ đi khi gom.
    const groupName = (t) => (t.metric === "khac" ? metricName(t).split(/\s[—–-]\s/)[0].trim() : metricName(t));
    const groups = new Map();
    items.forEach((t) => {
      const key = `${t.metric === "khac" ? `khac:${groupName(t)}` : t.metric}|${t.unit_label || ""}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(t);
    });
    const totals = [...groups.values()].filter((g) => g.length > 1 && g[0].unit_label !== "%" && g.every((t) => t.target_value > 0 && t.actual_value != null)).map((g) => {
      const target = g.reduce((s, t) => s + Number(t.target_value), 0), actual = g.reduce((s, t) => s + Number(t.actual_value), 0);
      return { key: `${g[0].metric === "khac" ? `khac:${groupName(g[0])}` : g[0].metric}|${g[0].unit_label || ""}`, ids: g.map((t) => t.id), name: groupName(g[0]), label: g[0].unit_label || "", count: g.length, target, actual, pct: Math.round((actual / target) * 1000) / 10 };
    });

    const collapsed = new Set();  // khoá các nhóm đang gom lại (chỉ còn dòng tổng)
    let filter = null, sortKey = null, sortDir = 1, openId = items.some((t) => t.id === focusId) ? focusId : null;  // trạng thái lọc / sắp xếp / dòng đang mở chi tiết
    const SORTS = {
      unit: (t) => t.unit_name || "Toàn công ty", metric: metricName, target: (t) => t.target_value ?? -1, actual: (t) => t.actual_value ?? -1,
      gap: (t) => (t.target_value == null || t.actual_value == null ? Infinity : t.target_value - t.actual_value),
      forecast: (t) => t.forecast_pct ?? -1, pct: (t) => t.pct ?? -1,
    };
    const bar = (pct, cls, mark) => `<div class="tp-bar"><i class="tp-${cls}" style="width:${Math.min(pct, 100)}%"></i>${mark != null ? `<b class="tp-mark" style="left:${mark}%" title="Thời gian đã qua: ${mark}%"></b>` : ""}</div>`;
    const SORT_LABELS = { unit: "Đơn vị", metric: "Chỉ tiêu", target: "Mục tiêu", actual: "Thực hiện", gap: "Còn thiếu", forecast: "Dự báo cuối kỳ", pct: "Tiến độ" };
    // Cột số bắt đầu bằng giảm dần (số lớn lên trước); cột chữ bắt đầu bằng tăng dần.
    const FIRST_DESC = new Set(["target", "actual", "gap", "forecast", "pct"]);
    const th = (key, label, cls = "") => {
      const on = sortKey === key;
      return `<th class="${cls}" aria-sort="${on ? (sortDir > 0 ? "ascending" : "descending") : "none"}"><button type="button" class="sort-btn" data-sort="${key}">${label}</button></th>`;
    };
    const detail = (t) => `<tr class="detail-row"><td colspan="8">
        <div class="tp-detail">
          <div><b>${esc(t.unit_name || "Toàn công ty")} · ${esc(metricName(t))}</b>
            ${t.unit_id ? `<button class="link" onclick="go('units',{unitId:${t.unit_id}})">Mở trang đơn vị →</button>` : ""}</div>
          ${t.notes ? `<p class="muted" style="margin:4px 0">${esc(t.notes)}</p>` : ""}
          <table class="mini"><tr><th>Kỳ</th><th class="num">Mục tiêu</th><th class="num">Thực hiện</th><th class="num">% đạt</th></tr>
            ${t.history.map((h) => `<tr class="${h.period === cur ? "cur" : ""}"><td>${esc(h.period)}</td><td class="num">${fmtMoney(h.target_value)}</td>
              <td class="num">${fmtMoney(h.actual_value)}</td><td class="num">${h.pct == null ? "—" : h.pct + "%"}</td></tr>`).join("")}
          </table>
        </div></td></tr>`;

    // Nhận xét tự động: đơn vị nào đang chậm hơn thời gian đã trôi qua của kỳ (so với "kỳ vọng" tuyến tính).
    const lagging = elapsed == null ? [] : items.filter((t) => t.pct != null && elapsed - t.pct >= 5)
      .map((t) => ({ t, gap: Math.round((elapsed - t.pct) * 10) / 10 })).sort((a, b) => b.gap - a.gap);
    const insightHtml = !lagging.length ? "" : `<ul class="tp-insights">${lagging.slice(0, 4).map(({ t, gap }) =>
      `<li><b>${esc(t.unit_name || "Toàn công ty")}</b> (${esc(metricName(t))}) chậm <b>${gap}</b> điểm so với kỳ vọng${t.forecast_pct != null ? `, dự báo cuối kỳ đạt ${t.forecast_pct}%` : ""}.</li>`).join("")}</ul>`;
    // Gửi số liệu đang hiển thị cho Trợ lý AI để nhận xét (số liệu đã lọc theo quyền của người xem)
    const askAI = () => {
      const r1 = (n) => Math.round(n * 10) / 10;
      const lines = items.map((t, i) => {
        const name = `${t.unit_name || "Toàn công ty"} · ${metricName(t)}`;
        if (t.pct == null) return `${i + 1}. ${name}: mục tiêu ${fmtMoney(t.target_value)}, CHƯA CÓ SỐ THỰC HIỆN.`;
        const parts = [`mục tiêu ${fmtMoney(t.target_value)}, thực hiện ${fmtMoney(t.actual_value)} (${t.pct}%)`, `trạng thái: ${STATUS[t.status][1]}`];
        if (elapsed != null) {
          parts.push(`so với kỳ vọng ${elapsed}%: ${t.pct >= elapsed ? "vượt" : "chậm"} ${r1(Math.abs(elapsed - t.pct))} điểm %`);
          const left = t.target_value - t.actual_value;
          if (left > 0 && elapsed > 0 && elapsed < 100 && t.actual_value > 0) {
            const need = left / (100 - elapsed), now = t.actual_value / elapsed;   // tốc độ theo từng 1% thời gian của kỳ
            parts.push(`còn thiếu ${fmtMoney(left)} trong ${r1(100 - elapsed)}% thời gian còn lại, cần tốc độ gấp ${r1(need / now)} lần tốc độ trung bình đến nay`);
          } else if (left <= 0) parts.push("đã đạt mục tiêu");
        }
        if (t.forecast_pct != null) parts.push(`dự báo cuối kỳ ${fmtMoney(t.forecast_value)} (${t.forecast_pct}% mục tiêu)`);
        const hist = (t.history || []).filter((h) => h.period !== cur && h.pct != null).slice(0, 3);
        if (hist.length) parts.push(`các kỳ trước: ${hist.map((h) => `${h.period} đạt ${h.pct}%`).join("; ")}`);
        if (t.notes) parts.push(`ghi chú: ${t.notes}`);
        return `${i + 1}. ${name}: ${parts.join("; ")}.`;
      });
      go("chat", { chatId: null, chatSeed: [
        `Bạn là chuyên gia phân tích kinh doanh, đang báo cáo cho CEO. Hãy nhận xét tiến độ mục tiêu kỳ ${cur}.`,
        "",
        "BỐI CẢNH",
        elapsed != null ? `- Đã qua ${elapsed}% thời gian của kỳ, nên kỳ vọng tuyến tính là đạt ${elapsed}% mục tiêu.` : "- Kỳ đã kết thúc hoặc chưa xác định thời gian đã qua.",
        `- Đơn vị tính: ${uLabel || "xem từng dòng"}. Ngưỡng trạng thái: Đạt từ 100%; Cần theo dõi từ 70% đến dưới 100%; Chậm dưới 70%.`,
        '- "Dự báo cuối kỳ" được ngoại suy tuyến tính theo tốc độ hiện tại, chưa tính thời vụ hay đơn hàng đã chốt, nên chỉ là tham khảo.',
        "",
        "SỐ LIỆU",
        ...lines,
        "",
        "YÊU CẦU TRẢ LỜI (tiếng Việt, ngắn gọn, dành cho CEO, tối đa khoảng 250 từ)",
        "1. Kết luận một câu về tình hình chung.",
        "2. Đơn vị nào chậm so với kỳ vọng thời gian (nêu số điểm % chậm), xếp từ nặng đến nhẹ.",
        "3. Đơn vị nào có nguy cơ không đạt mục tiêu cuối kỳ và vì sao (dựa vào dự báo, mức còn thiếu và tốc độ cần thiết).",
        "4. 2-3 việc cần làm cụ thể, mỗi việc ghi rõ đơn vị nào, làm gì, và nên hoàn thành trước khi nào.",
        "Chỉ dùng số liệu ở trên, không bịa thêm số. Nếu dữ liệu thiếu hoặc chưa đủ để kết luận (ví dụ dòng chưa có số), hãy nói rõ thay vì đoán.",
      ].join("\n") });
    };

    const draw = () => {
      const hidden = new Set(filter ? [] : totals.filter((g) => collapsed.has(g.key)).flatMap((g) => g.ids));
      let list = (filter ? items.filter((t) => t.status === filter) : items.slice()).filter((t) => !hidden.has(t.id));
      // Mặc định: đơn vị chậm nhất (% đạt thấp nhất) lên đầu; dòng chưa có số xuống cuối.
      if (!sortKey) list.sort((a, b) => (a.pct ?? Infinity) - (b.pct ?? Infinity));
      else list.sort((a, b) => { const x = SORTS[sortKey](a), y = SORTS[sortKey](b); return (x > y ? 1 : x < y ? -1 : 0) * sortDir; });
      main.querySelector("#tp-kpis").innerHTML = tiles.map(([k, label]) => `<button type="button" class="card kpi ${STATUS[k][0]} ${filter === k ? "active" : ""} ${summary[k] ? "" : "zero"}" data-filter="${k}" aria-pressed="${filter === k}" ${summary[k] || filter === k ? "" : "disabled"}>
        <div class="kpi-num">${summary[k]}</div><div class="kpi-lbl">${label}</div></button>`).join("");
      main.querySelector("#tp-table").innerHTML = `
        <tr>${th("unit", "Đơn vị")}${th("metric", "Chỉ tiêu")}${th("target", `Mục tiêu${uLabel ? ` (${esc(uLabel)})` : ""}`, "num")}${th("actual", "Thực hiện", "num")}${th("gap", "Còn thiếu", "num")}${th("forecast", "Dự báo cuối kỳ", "num")}${th("pct", "Tiến độ")}<th>Trạng thái</th>${canEdit ? "<th></th>" : ""}</tr>
        ${list.length || hidden.size ? list.map((t) => `
          <tr class="clickable ${openId === t.id ? "open" : ""}" data-row="${t.id}" tabindex="0" aria-expanded="${openId === t.id}">
            <td>${esc(t.unit_name || "Toàn công ty")}</td>
            <td>${esc(metricName(t))}</td>
            <td class="num" title="${fmtNum(t.target_value)}">${fmtMoney(t.target_value)}${uLabel ? "" : ` <span class="muted">${esc(t.unit_label || "")}</span>`}</td>
            <td class="num" title="${fmtNum(t.actual_value)}">${fmtMoney(t.actual_value)}</td>
            <td class="num">${gapCell(t)}</td>
            <td class="num">${forecastCell(t)}</td>
            <td>${t.pct == null ? '<span class="muted">—</span>' : `${bar(t.pct, t.status, elapsed)}<small>${t.pct}%</small>`}</td>
            <td><span class="badge ${STATUS[t.status][0]}">${STATUS[t.status][1]}</span></td>
            ${canEdit ? `<td class="row-actions"><button type="button" class="row-icon-btn" data-tp-edit="${t.id}" title="Sửa mục tiêu" aria-label="Sửa mục tiêu">${icon("edit")}</button><button type="button" class="row-icon-btn danger" data-tp-del="${t.id}" title="Xoá mục tiêu" aria-label="Xoá mục tiêu">${icon("trash")}</button></td>` : ""}
          </tr>${openId === t.id ? detail(t) : ""}`).join("") : `<tr><td colspan="${canEdit ? 9 : 8}" class="empty">Không có dòng nào ở trạng thái này.</td></tr>`}
        ${!filter ? totals.map((g) => `<tr class="total-row clickable" data-group="${esc(g.key)}" tabindex="0" aria-expanded="${!collapsed.has(g.key)}"><td colspan="2"><span class="grp-caret">${collapsed.has(g.key) ? "▸" : "▾"}</span> Tổng cộng · ${esc(g.name)} <span class="muted">(${g.count} đơn vị)</span></td><td class="num">${fmtMoney(g.target, g.label)}${uLabel ? "" : ` <span class="muted">${esc(g.label)}</span>`}</td><td class="num">${fmtMoney(g.actual, g.label)}</td>
          <td class="num">${g.target > g.actual ? fmtMoney(g.target - g.actual, g.label) : "—"}</td><td></td>
          <td>${bar(g.pct, g.pct >= 100 ? "ok" : g.pct >= 70 ? "watch" : "behind", elapsed)}<small>${g.pct}%</small></td><td></td>${canEdit ? "<td></td>" : ""}</tr>`).join("") : ""}`;
      main.querySelectorAll("[data-filter]").forEach((b) => (b.onclick = () => { filter = filter === b.dataset.filter ? null : b.dataset.filter; draw(); }));
      main.querySelectorAll("[data-group]").forEach((r) => {
        const toggle = () => { const k = r.dataset.group; collapsed.has(k) ? collapsed.delete(k) : collapsed.add(k); draw(); };
        r.onclick = toggle;
        r.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } };
      });
      const sortBar = main.querySelector("#tp-sortbar");
      sortBar.innerHTML = (totals.length && !filter ? `<span class="grp-actions"><button type="button" class="link" id="tp-collapse-all">Gom tất cả</button><button type="button" class="link" id="tp-expand-all">Mở tất cả</button></span>` : "") + (sortKey
        ? `<span>Đang sắp xếp theo <b>${SORT_LABELS[sortKey]}</b>, ${sortDir > 0 ? "tăng dần" : "giảm dần"}</span><button type="button" class="link" id="tp-sort-reset">Về mặc định</button>`
        : '<span class="muted">Mặc định: đơn vị chậm nhất lên đầu. Bấm tiêu đề cột để sắp xếp.</span>');
      sortBar.querySelector("#tp-collapse-all")?.addEventListener("click", () => { totals.forEach((g) => collapsed.add(g.key)); draw(); });
      sortBar.querySelector("#tp-expand-all")?.addEventListener("click", () => { collapsed.clear(); draw(); });
      sortBar.querySelector("#tp-sort-reset")?.addEventListener("click", () => { sortKey = null; sortDir = 1; draw(); });
      // Bấm lần đầu theo chiều phù hợp kiểu dữ liệu, bấm lại thì đảo chiều; nút Về mặc định nằm trên bảng.
      main.querySelectorAll("[data-sort]").forEach((h) => (h.onclick = () => {
        const key = h.dataset.sort;
        if (sortKey !== key) { sortKey = key; sortDir = FIRST_DESC.has(key) ? -1 : 1; } else sortDir = -sortDir;
        draw();
        main.querySelector(`[data-sort="${key}"]`)?.focus();   // giữ tiêu điểm cho người dùng bàn phím
      }));
      main.querySelectorAll("[data-row]").forEach((r) => {
        const toggle = () => { openId = openId == r.dataset.row ? null : Number(r.dataset.row); draw(); };
        r.onclick = toggle;
        r.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } };
      });
      // Nút Sửa/Xoá nằm trong dòng: chặn sự kiện để không mở chi tiết dòng
      main.querySelectorAll("[data-tp-edit]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); targetForm(items.find((t) => t.id == b.dataset.tpEdit)); }));
      main.querySelectorAll("[data-tp-del]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); confirmDelete("targets", b.dataset.tpDel, "mục tiêu này", reload); }));
    };

    // Bảng theo quý của năm đang chọn: mỗi dòng là một chỉ tiêu của một đơn vị. Cột "Cả năm": mục tiêu lấy từ dòng cả năm
    // (không có thì cộng mục tiêu các quý); thực hiện là lũy kế các quý. Chỉ tiêu % không cộng được nên chỉ lấy dòng cả năm.
    const quarterHtml = () => {
      const year = periodValues(cur).year, QS = ["Q1", "Q2", "Q3", "Q4"];
      const rowsByKey = new Map();
      allTargets.filter((t) => t.period === year || t.period.startsWith(`${year}-Q`)).forEach((t) => {
        const key = `${t.unit_id ?? ""}|${t.metric === "khac" ? t.metric_name : t.metric}|${t.unit_label || ""}`;
        if (!rowsByKey.has(key)) rowsByKey.set(key, { t, q: {}, year: null });
        const r = rowsByKey.get(key);
        if (t.period === year) r.year = t; else r.q[t.period.slice(-2)] = t;
      });
      const order = (t) => (KEY_METRICS.includes(t.metric) ? KEY_METRICS.indexOf(t.metric) : KEY_METRICS.length);
      const list = [...rowsByKey.values()].filter((r) => Object.keys(r.q).length)
        .sort((a, b) => order(a.t) - order(b.t) || String(a.t.unit_name || "").localeCompare(String(b.t.unit_name || ""), "vi"));
      const head = `<div class="tq-head"><h3 style="margin:0">Theo quý · năm ${esc(year)}</h3><span class="muted">Thêm mục tiêu với Kỳ = Quý 1 đến Quý 4 để có số từng quý.</span></div>`;
      if (!list.length) return `<div class="card" style="margin-top:16px">${head}<div class="empty">Năm ${esc(year)} chưa có số theo quý.</div></div>`;
      const cell = (t, label) => {
        if (!t || (t.target_value == null && t.actual_value == null)) return '<span class="muted">—</span>';
        const sfx = label === "%" ? "%" : "", pct = t.target_value > 0 && t.actual_value != null ? ` · ${Math.round((t.actual_value / t.target_value) * 100)}%` : "";
        const unit = (v) => (v == null ? "" : sfx);
        return `${fmtMoney(t.actual_value, label)}${unit(t.actual_value)}<small class="muted">/ ${fmtMoney(t.target_value, label)}${unit(t.target_value)}${pct}</small>`;
      };
      const yearCell = (r, label) => {
        const qs = QS.map((k) => r.q[k]).filter(Boolean);
        if (label === "%") return cell(r.year, label);
        const sum = (f) => { const v = qs.map((t) => t[f]).filter((x) => x != null); return v.length ? v.reduce((s, x) => s + Number(x), 0) : null; };
        const qTargets = qs.map((t) => t.target_value);
        return cell({ actual_value: sum("actual_value"), target_value: r.year?.target_value ?? (qTargets.every((x) => x != null) ? sum("target_value") : null) }, label);
      };
      return `<div class="card tq" style="margin-top:16px">${head}<div class="table-scroll"><table>
        <tr><th>Chỉ tiêu</th><th>Đơn vị</th>${QS.map((k, i) => `<th class="num">Quý ${i + 1}</th>`).join("")}<th class="num">Cả năm (lũy kế)</th></tr>
        ${list.map((r) => { const label = r.t.unit_label || ""; return `<tr><td>${esc(metricName(r.t))}</td><td>${esc(r.t.unit_name || "Toàn công ty")}</td>
          ${QS.map((k) => `<td class="num">${cell(r.q[k], label)}</td>`).join("")}<td class="num">${yearCell(r, label)}</td></tr>`; }).join("")}
      </table></div></div>`;
    };

    main.innerHTML = `
      <div class="page-head"><div><h2>Mục tiêu trọng yếu</h2>
        <p>Thực hiện so với mục tiêu theo kỳ. Đạt từ 100%; từ 70% đến dưới 100% là cần theo dõi; dưới 70% là chậm.
          Chỉ hiện mục tiêu của các đơn vị bạn được xem.</p></div>
        <div class="head-actions">
          ${canEdit ? '<button type="button" class="primary" id="tp-add">+ Thêm mục tiêu</button>' : ""}
          ${items.length ? `<a class="ghost btn-link" id="tp-xlsx" href="/api/targets/export?period=${encodeURIComponent(cur)}" download>Xuất Excel</a>
            <button type="button" class="ghost" id="tp-print">In / lưu PDF</button>
            ${canSee("chat") ? `<button type="button" class="primary accent" id="tp-ai">${icon("spark")} Hỏi Trợ lý AI</button>` : ""}` : ""}
          ${periods.length ? `<label class="period-pick"><span>Kỳ báo cáo</span><select id="tp-period" aria-label="Chọn kỳ">${periods.map((p) => `<option ${p === cur ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></label>` : ""}</div></div>
      ${!items.length ? `<div class="card empty">${periods.length ? "Kỳ này chưa có mục tiêu." : "Chưa có mục tiêu nào trong phạm vi bạn được xem. Mục tiêu được nhập trong trang Phòng ban, tab Mục tiêu."}</div>` : `
        <div class="kpis" id="tp-kpis"></div>
        ${elapsed != null ? `<p class="muted tp-elapsed">Đã qua <b>${elapsed}%</b> thời gian của kỳ ${esc(cur)} (vạch đen trên thanh tiến độ). Dự báo cuối kỳ tính theo tốc độ hiện tại. Bấm một dòng để xem chi tiết, bấm thẻ để lọc, bấm tiêu đề cột để sắp xếp.</p>` : ""}
        ${insightHtml}
        <div class="card" style="margin-top:16px"><div class="sort-bar" id="tp-sortbar"></div><table id="tp-table"></table></div>`}
      ${quarterHtml()}`;
    main.querySelector("#tp-add")?.addEventListener("click", () => targetForm());
    const sel = main.querySelector("#tp-period");
    if (sel) sel.onchange = () => VIEWS.targets(main, sel.value);
    if (items.length) {
      main.querySelector("#tp-print").onclick = () => window.print();
      main.querySelector("#tp-ai")?.addEventListener("click", askAI);
      draw();
      if (openId) main.querySelector(`[data-row="${openId}"]`)?.scrollIntoView({ block: "center" });
    }
  },

  async insights(main) {
    const ins = await api("/api/insights");
    const unitLink = (id, name) => `<button class="link" onclick="go('units',{unitId:${id}})">${esc(name)}</button>`;
    const clean = [];  // mục không có gì để báo: gom thành một dòng thay vì mỗi mục một thẻ trống
    const block = (title, items, fmt, note) => {
      if (!items.length) { clean.push(title); return ""; }
      return `<div class="card insight">
        <h3>${title} <span class="badge">${items.length}</span></h3>
        ${note ? `<p class="muted">${note}</p>` : ""}
        <ul>${items.map(fmt).join("")}</ul>
      </div>`;
    };
    const lead = (key, label) => {
      const g = ins.leadership[key];
      return `<details class="card lead-card"><summary><span class="lead-n">${g.count}</span><span class="lead-l">${label}</span></summary>
        <ul class="lead-list">${g.people.map((p) => `<li><b>${esc(p.name)}</b> <span class="muted">${esc(p.title)}</span> ${unitLink(p.unit_id, p.unit_name)}</li>`).join("") || '<li class="muted">Chưa có ai</li>'}</ul></details>`;
    };
    main.innerHTML = `
      <div class="page-head"><div><h2>Phân tích cơ cấu tổ chức</h2>
        <p>Các chỉ dấu dưới đây được tính trực tiếp từ dữ liệu, chưa phải kết luận. Hỏi Trợ lý AI để có đánh giá và đề xuất.</p></div>
        ${canSee("chat") ? `<button class="primary accent" onclick="go('chat')">${icon("spark")} Hỏi Trợ lý AI</button>` : ""}</div>
      <div class="lead-row">${lead("heads", "Trưởng phòng / ban")}${lead("deputies", "Phó phòng / ban")}</div>
      <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(340px, 1fr))">
        ${block("Người kiêm nhiệm nhiều đơn vị", ins.concurrent_roles, (x) => {
          const byTitle = {};  // gom chức danh trùng: "PTGĐ – A; PTGĐ – B" thành "PTGĐ: A, B"
          const reportsTo = {};  // chức danh nào báo cáo cho ai: ghi một lần cho cả nhóm
          x.role_items.forEach((r) => {
            (byTitle[r.title] ||= []).push(r);
            if (r.reports_to) reportsTo[r.title] = r.reports_to;
          });
          const chip = (id, name) => `<button type="button" class="chip chip-link" title="Mở ${esc(name)}" onclick="go('units',{unitId:${id}})">${esc(name)}</button>`;
          const total = (x.manages || []).reduce((n, m) => n + m.units.length, 0);
          const groups = (x.manages || []).map((m) => `<div class="mg-row"><span class="mg-via">${esc(m.via)}</span>
            <span class="chips">${m.units.map((u, i) => chip(m.unit_ids[i], u)).join("")}</span></div>`).join("");
          return `<li class="person"><div class="p-name">${esc(x.name)}</div>
            ${Object.entries(byTitle).map(([t, rs]) => `<div class="p-role"><b>${esc(t)}</b> <span class="chips">${rs.map((r) => chip(r.unit_id, r.unit_name)).join("")}</span>${reportsTo[t] ? ` <span class="muted">→ báo cáo <b>${esc(reportsTo[t])}</b></span>` : ""}</div>`).join("")}
            ${total ? `<details class="p-manages" ${total <= 6 ? "open" : ""}><summary>Quản lý trực tiếp <span class="badge">${total}</span></summary>${groups}</details>` : ""}</li>`;
        },
          "Kiêm nhiệm giúp tiết kiệm chi phí nhưng tạo rủi ro quá tải và xung đột lợi ích (đặc biệt kiểm soát nội bộ vs tài chính).")}
        ${block("Vị trí đang trống (TBA)", ins.vacancies, (x) => `<li>${esc(x.title)} – ${unitLink(x.unit_id, x.unit_name)}${x.reports_to ? ` · báo cáo <b>${esc(x.reports_to)}</b>` : ""}</li>`,
          "Khi vị trí đứng đầu còn trống, cấp trên trực tiếp đang quản lý đơn vị.")}
        ${block("Phòng/ban do cấp phó phụ trách", ins.deputy_led_departments, (x) => `<li>${unitLink(x.unit_id, x.unit_name)} – ${esc(x.title)} ${esc(x.name || "TBA")}${x.reports_to ? ` · báo cáo <b>${esc(x.reports_to)}</b>` : ""}</li>`,
          "Chưa có Trưởng phòng – cân nhắc bổ nhiệm hoặc xác nhận đây là chủ trương.")}
        ${block("Tầm hạn quản lý (số đơn vị trực tiếp)", ins.span_of_control, (x) => `<li>${unitLink(x.unit_id, x.unit_name)}: <b>${x.direct_reports}</b>
          <span>· ${esc(x.head || "chưa có người đứng đầu")}${x.reports_to ? ` · báo cáo ${esc(x.reports_to)}` : ""}</span></li>`)}
        ${block("Phòng/ban chưa có quy trình", ins.units_without_process, (x) => `<li>${unitLink(x.unit_id, x.unit_name)}${x.reports_to ? ` · báo cáo <b>${esc(x.reports_to)}</b>` : ""}</li>`)}
        ${block("Dữ liệu cần xác nhận", [...ins.unverified.units.map((u) => ({ ...u, k: "u" })), ...ins.unverified.employees.map((e) => ({ ...e, k: "e" }))],
          (x) => (x.k === "u" ? `<li>${unitLink(x.id, x.name)}: ${esc(x.full_name || "")}</li>` : `<li>Nhân sự: ${esc(x.full_name)}</li>`))}
        ${block("Quy trình cần rà soát", ins.stale_processes, (x) => `<li>${unitLink(x.unit_id, x.unit_name)}: ${esc((x.code ? x.code + " – " : "") + x.name)}
          <span class="muted">${x.effective_date ? "hiệu lực " + esc(x.effective_date) : "chưa có ngày hiệu lực"}</span></li>`,
          "Quy trình chưa rà soát quá 12 tháng hoặc chưa ghi ngày hiệu lực.")}
        ${block("Tài liệu nội bộ cần rà soát", ins.stale_documents, (x) => `<li>${esc((x.code ? x.code + " – " : "") + x.title)}
          <span class="muted">${esc(x.unit_name || "Chung công ty")} · tải lên ${esc(String(x.uploaded_at).slice(0, 10))}</span></li>`,
          "Tài liệu ISO, quy định, biểu mẫu tải lên quá 12 tháng. Nên xem lại và tải bản mới nếu có thay đổi.")}
        ${block("Quy trình đang là bản nháp", ins.draft_processes, (x) => `<li>${unitLink(x.unit_id, x.unit_name)}: ${esc(x.name)}</li>`)}
      </div>
      ${clean.length ? `<p class="insight-clean">✓ Không phát hiện vấn đề ở: ${clean.map(esc).join(" · ")}</p>` : ""}
      <div class="card" style="margin-top:16px">
        <h3>Biên chế theo đơn vị</h3>
        <p class="muted">Định biên là tổng số người theo sơ đồ. Nhân sự HCNS là số người đang gán vào đơn vị trong danh sách HCNS.
          Chênh lệch âm là thiếu so với định biên; dương là dư. Chỉ là đối chiếu số liệu hiện có, chưa phải dự báo.</p>
        <table>
          <tr><th>Đơn vị</th><th class="num">Định biên</th><th class="num">Đã gán trên sơ đồ</th><th class="num">Còn trống</th><th class="num">Nhân sự HCNS</th><th class="num">Chênh lệch</th></tr>
          ${ins.staffing.map((s) => `<tr>
            <td>${unitLink(s.unit_id, s.unit_name)}${s.reports_to ? `<br><small>báo cáo ${esc(s.reports_to)}</small>` : ""}</td>
            <td class="num">${s.planned}</td><td class="num">${s.seated}</td>
            <td class="num">${s.open_on_chart ? `<span class="badge warn">${s.open_on_chart}</span>` : "0"}</td>
            <td class="num">${s.hcns_active}</td>
            <td class="num">${s.gap === 0 ? "0" : `<span class="badge ${s.gap < 0 ? "bad" : "brand"}">${s.gap > 0 ? "+" : ""}${s.gap}</span>`}</td>
          </tr>`).join("")}
        </table>
      </div>`;
  },

  async docs(main) {
    const [docs, meta, units] = await Promise.all([api("/api/documents"), api("/api/documents/meta"), api("/api/units")]);
    main.innerHTML = `
      <div class="toolbar"><h2 style="margin:0">Kho tài liệu (${docs.length})</h2>
        ${can("docs_edit") ? DOC_ACTIONS : ""}</div>
      <p class="muted">Quy trình ISO, hướng dẫn, biểu mẫu, quy định. Tối đa ${meta.max_mb} MB mỗi file; PDF scan được AI đọc
        ${meta.ocr_available ? "" : '<span class="badge warn">cần khoá Anthropic API</span>'}
        <span class="doc-formats" title="${esc(meta.allowed_ext.join(", "))}">· Định dạng hỗ trợ</span></p>
      ${(() => {
        const unread = docs.filter((d) => DOC_UNREAD.has(d.extract_status));
        const failed = unread.filter((d) => d.extract_status === "failed").length;
        return unread.length ? `<div class="unread-banner"><span>⚠ <b>${unread.length} tài liệu chưa đọc được</b> – trợ lý AI chưa trả lời được từ nội dung ${unread.length > 1 ? "các file này" : "file này"}.</span>
          <span class="ub-acts"><button class="link" id="doc-show-unread">Chỉ hiện ${unread.length > 1 ? "các file này" : "file này"}</button>
          ${failed && can("docs_edit") ? `<button class="link" id="doc-reprocess-all">Đọc lại ${failed} file lỗi</button>` : ""}</span></div>` : "";
      })()}
      ${(() => {
        const n = docs.filter(needsReview).length;
        return n ? `<div class="review-banner"><span><b>${n} tài liệu</b> AI đọc từ bản scan, cần đối chiếu với bản gốc.</span>
          <button class="link" id="doc-show-review">Chỉ hiện các file này</button></div>` : "";
      })()}
      <div class="card" style="margin-bottom:16px">
        <form id="doc-search" class="chat-input" style="margin:0">
          <input name="q" autocomplete="off" placeholder="${state.docContent ? "Tìm theo tên file và nội dung" : "Tìm theo tên file"} (không cần gõ dấu)..." value="${esc(state.docQuery)}"
                 style="flex:1;padding:8px;border:1px solid var(--line);border-radius:8px">
          <button class="primary">Tìm</button>
        </form>
        <label class="muted small" style="display:inline-flex;gap:6px;align-items:center;margin-top:8px;cursor:pointer">
          <input type="checkbox" id="doc-in-content" ${state.docContent ? "checked" : ""}> Tìm cả trong nội dung tài liệu (có thể ra nhiều kết quả)
        </label>
        <div class="doc-filters" id="doc-filters">
          <select name="unit"><option value="">Tất cả đơn vị</option><option value="none">Tài liệu chung</option>
            ${[...new Map(docs.filter((d) => d.unit_id).map((d) => [d.unit_id, d.unit_name])).entries()].sort((a, b) => a[1].localeCompare(b[1], "vi"))
              .map(([id, n]) => `<option value="${id}">${esc(n)}</option>`).join("")}</select>
          <select name="type"><option value="">Tất cả loại</option>
            ${Object.entries(DOC_LABELS).filter(([k]) => docs.some((d) => d.doc_type === k)).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select>
          <select name="status"><option value="">Mọi trạng thái</option>
            ${docs.some((d) => DOC_UNREAD.has(d.extract_status)) ? '<option value="unread">Chưa đọc được</option>' : ""}
            ${docs.some(isUnreviewed) ? '<option value="unreviewed">Cần đối chiếu bản gốc</option>' : ""}
            ${docs.some(cannotReview) ? '<option value="noreview">Không mở được đối chiếu</option>' : ""}
            ${docs.some(hasWarnNote) ? '<option value="warn">Cần kiểm tra lại</option>' : ""}
            ${docs.some(reviewDone) ? '<option value="reviewed">Đã đối chiếu</option>' : ""}</select>
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
      (!F.status || (F.status === "unread" ? DOC_UNREAD.has(d.extract_status)
        : F.status === "unreviewed" ? isUnreviewed(d) : F.status === "noreview" ? cannotReview(d)
        : F.status === "warn" ? hasWarnNote(d) : reviewDone(d))));
    const filtering = () => !!(F.unit || F.type || F.status);
    const renderAll = () => {
      const list = filt(docs);
      $("#doc-all").innerHTML = list.length ? docTable(list, true) : '<div class="empty">Không có tài liệu nào khớp bộ lọc.</div>';
      $("#doc-filter-reset").hidden = !filtering();
      $("#doc-filter-count").textContent = filtering() && !state.docQuery.trim() ? `${list.length}/${docs.length} tài liệu` : "";
      if (!$("#doc-all").hidden) bindDocActions($("#doc-all"), meta, units);
    };
    // Nút ở banner bật/tắt bộ lọc: bấm lần nữa thì bỏ lọc
    const bannerToggle = (btn, status) => {
      if (!btn) return;
      btn.onclick = () => {
        F.status = F.status === status ? "" : status;
        const st = document.querySelector('#doc-filters select[name="status"]');
        st.value = F.status;
        st.dispatchEvent(new Event("sync"));
        renderAll();
      };
    };
    bannerToggle($("#doc-show-unread"), "unread");
    bannerToggle($("#doc-show-review"), "unreviewed");
    const reprocAllBtn = $("#doc-reprocess-all");
    if (reprocAllBtn) reprocAllBtn.onclick = async () => {
      if (!(await confirmBox("Đọc lại các file lỗi?", "Hệ thống đọc lần lượt từng file và có thể tốn hạn mức AI. Nếu hết hạn mức, phần còn lại sẽ dừng và đọc lại sau.", { okText: "Đọc lại" }))) return;
      try {
        const r = await api("/api/documents/reprocess-unread", { method: "POST" });
        toast(`Đã đưa ${r.queued} file vào hàng đợi đọc lại.`);
        render();
      } catch (e) { toast(e.message, "err"); }
    };
    document.querySelectorAll("#doc-filters select").forEach((sel) => {
      sel.value = F[sel.name];
      sel.onchange = () => { F[sel.name] = sel.value; renderAll(); showHits(); };
      enhanceSelect(sel, { searchable: sel.name === "unit" });
    });
    $("#doc-filter-reset").onclick = () => {
      Object.assign(F, { unit: "", type: "", status: "" });
      document.querySelectorAll("#doc-filters select").forEach((x) => { x.value = ""; x.dispatchEvent(new Event("sync")); });
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
      const hits = filt(await api(`/api/documents/search?q=${encodeURIComponent(q)}${state.docContent ? "&content=true" : ""}`));
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
    $("#doc-in-content").onchange = (e) => {
      state.docContent = e.target.checked;
      qInput.placeholder = `${state.docContent ? "Tìm theo tên file và nội dung" : "Tìm theo tên file"} (không cần gõ dấu)...`;
      showHits();
    };
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
    const isAdmin = state.user.role === "admin";
    const pendingActions = (x) => `<button class="link" data-approve="${x.id}">Duyệt</button> · <button class="link danger" data-del="${x.id}" data-user="${esc(x.username)}">Từ chối</button>`;
    main.innerHTML = `
      <div class="toolbar"><h2 style="margin:0">Tài khoản (${users.length})</h2>${isAdmin ? '<button class="primary" id="add-user">+ Tạo tài khoản</button>' : ""}</div>
      <div class="card">
        <table>
          <tr><th>Tên đăng nhập</th><th>Họ tên</th><th>Hồ sơ nhân sự</th><th>Vai trò</th><th>Đơn vị phụ trách</th><th>Quyền cấp thêm</th><th>Dung lượng riêng</th><th>Trạng thái</th><th></th></tr>
          ${users.map((x) => `<tr><td>${esc(x.username)}</td><td>${esc(x.full_name || "")}${x.pending_approval && (x.register_unit || x.register_note) ? `<div class="muted small">${esc([x.register_unit || x.register_note, x.register_phone ? `máy lẻ ${x.register_phone}` : ""].filter(Boolean).join(" · "))}</div>` : ""}</td><td>${x.employee_name ? esc(x.employee_name) : '<span class="badge warn">Chưa gán</span>'}</td><td>${esc(state.roles[x.role])}</td>
            <td>${esc(x.unit_name || "—")}</td><td>${["admin", "ceo"].includes(x.role) ? '<span class="muted">Mặc định có đủ</span>' : (x.granted.map((f) => esc(FEATURE_LABELS[f])).join(", ") || '<span class="muted">—</span>')}</td><td>${["admin", "ceo"].includes(x.role) ? '<span class="muted">Không giới hạn</span>' : `${fmtSize(x.private_bytes) || "0 KB"} / ${x.quota_mb || 300} MB`}</td><td>${x.pending_approval ? '<span class="badge warn">Chờ duyệt</span>' : x.active ? '<span class="badge ok">Hoạt động</span>' : '<span class="badge warn">Đã khoá</span>'}${x.locked ? ' <span class="badge warn">Sai mật khẩu nhiều lần</span>' : ""}</td>
            <td style="white-space:nowrap">${x.pending_approval ? pendingActions(x) : `${isAdmin ? `<button class="link" data-edit="${x.id}">Sửa</button> · <button class="link" data-link="${x.id}">Gán hồ sơ</button>${["admin", "ceo"].includes(x.role) ? "" : ` · <button class="link" data-perm="${x.id}">Cấp quyền</button>`}` : ""}${x.role === "viewer" ? "" : `${isAdmin ? " · " : ""}<button class="link" data-mem="${x.id}">Ghi chú AI</button>`}${isAdmin && x.locked ? ` · <button class="link" data-unlock="${x.id}">Mở khoá đăng nhập</button>` : ""}${x.id !== state.user.id ? `${isAdmin || x.role !== "viewer" ? " · " : ""}<button class="link danger" data-del="${x.id}" data-user="${esc(x.username)}">Xoá</button>` : ""}`}</td></tr>`).join("")}
        </table>
      </div>
      <div class="card" style="margin-top:16px">
        <h3>Phân quyền</h3>
        <table>
          <tr><th>Vai trò</th><th>Xem</th><th>Chỉnh sửa</th><th>Trợ lý AI</th></tr>
          <tr><td colspan="4" class="muted">Tài liệu, Phân tích và Nhập file HCNS: chỉ admin/Ban TGĐ mặc định có; các tài khoản khác cần được cấp ở nút "Cấp quyền".</td></tr>
          <tr><td>Quản trị hệ thống</td><td>Tất cả</td><td>Tất cả + tài khoản</td><td>Có</td></tr>
          <tr><td>Ban Tổng Giám đốc</td><td>Tất cả</td><td>Tất cả</td><td>Có</td></tr>
          <tr><td>Quản lý đơn vị</td><td>Sơ đồ, phòng ban, nhân sự</td><td>Đơn vị mình + đơn vị con: chức danh, quy trình, mục tiêu (tài liệu: cần được cấp)</td><td>Có</td></tr>
          <tr><td>Chỉ xem</td><td>Sơ đồ, phòng ban, nhân sự</td><td>Không</td><td>Không (cấp quyền "Dùng trợ lý AI" nếu cần)</td></tr>
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
    if (isAdmin) $("#add-user").onclick = async () => {
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
    main.querySelectorAll("[data-approve]").forEach((b) => (b.onclick = () => {
      const x = users.find((y) => y.id == b.dataset.approve);
      openForm(`Duyệt tài khoản ${x.username}`, [
        { name: "role", label: "Vai trò", type: "select", options: Object.entries(state.roles), default: "viewer" },
        { name: "unit_id", label: "Đơn vị phụ trách (cho vai trò Quản lý đơn vị)", type: "select", numeric: true, options: [["", "— Không —"], ...units.map((u) => [u.id, u.name])] },
        tplField,
        ...permFields(),
      ], { role: "viewer" }, (d) => api(`/api/users/${x.id}/approve`, { method: "POST", body: {
        role: d.role, unit_id: d.unit_id, features: pickedFeatures(d),
      } }).then(() => { toast(`Đã duyệt tài khoản ${x.username}.`); refreshPending(); }), "Duyệt");
      bindPermForm();
    }));
    main.querySelectorAll("[data-unlock]").forEach((b) => (b.onclick = async () => {
      try { await api(`/api/users/${b.dataset.unlock}/unlock`, { method: "POST" }); render(); } catch (e) { toast(e.message, "err"); }
    }));
    main.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      const typed = await ask({ title: `Xoá vĩnh viễn tài khoản ${b.dataset.user}?`, message: "Tài khoản sẽ bị xoá ngay và đăng xuất. Toàn bộ file riêng, ghi chú AI và lịch sử chat của tài khoản này sẽ bị xoá, không thể khôi phục. Tài liệu đã đưa lên thư viện chung được giữ lại. Gõ lại tên đăng nhập để xác nhận.", input: "", okText: "Xoá tài khoản", danger: true });
      if (!typed) return;
      try {
        await api(`/api/users/${b.dataset.del}`, { method: "DELETE", body: { confirm: typed } });
        toast(`Đã xoá tài khoản ${b.dataset.user}.`);
        render();
      } catch (e) { toast(e.message, "err"); }
    }));
    main.querySelectorAll("[data-perm]").forEach((b) => (b.onclick = () => {
      const x = users.find((y) => y.id == b.dataset.perm);
      openForm(`Cấp quyền cho ${x.username}`, [tplField, ...permFields()], permValues(x.granted),
      (d) => api(`/api/users/${x.id}/permissions`, { method: "PUT", body: { features: pickedFeatures(d) } }));
      bindPermForm();
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

  // Ngân sách hoạt động 2026: mốc so sánh là cột "tổng duyệt" cộng phần TGĐ duyệt bổ sung; cảnh báo tính ở backend (opbudget.py)
  async budget(main) {
    const r = await api("/api/budget" + (state.bkMonth ? `?month=${state.bkMonth}` : ""));
    const pickFile = (accept, url, done) => {
      const inp = document.createElement("input");
      inp.type = "file"; inp.accept = accept;
      inp.onchange = async () => {
        if (!inp.files[0]) return;
        const fd = new FormData();
        fd.append("file", inp.files[0]);
        try { done(await api(url, { method: "POST", body: fd })); } catch (e) { toast(e.message, "err"); }
      };
      inp.click();
    };
    const importPlan = () => pickFile(".xls,.xlsx,.xlsm", "/api/budget/plan/import", (res) => {
      toast(`Đã nhập ${res.lines} hạng mục, tổng ngân sách duyệt ${(res.total / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tỷ.`);
      VIEWS.budget(main);
    });
    if (!r.has_plan) {
      main.innerHTML = `<div class="card"><h3>Ngân sách hoạt động ${r.year}</h3>
        <p class="muted">Chưa có kế hoạch ngân sách. Nhập file "Bản duyệt ngân sách hoạt động ${r.year}" (Excel) để dựng bảng theo dõi. Chỉ lấy sheet TỔNG HỢP, cột tổng duyệt năm ${r.year}; số năm trước không được đưa vào.</p>
        <button class="primary" id="bk-plan">${icon("upload")}Nhập kế hoạch từ Excel</button></div>`;
      $("#bk-plan").onclick = importPlan;
      return;
    }
    const m = r.as_of, T = r.totals;
    const bn = (n) => {  // số tiền ngắn gọn: tỷ / triệu
      n = Number(n || 0);
      const a = Math.abs(n);
      if (a >= 1e9) return (n / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 2 }) + " tỷ";
      if (a >= 1e6) return (n / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " triệu";
      return fmtNum(Math.round(n)) + " đ";
    };
    const dong = (n) => fmtNum(Math.round(n)) + " đ";
    const tr = (n) => (Math.abs(n) < 0.5 ? "—" : (n / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 }));
    const pc = (n) => Number(n).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + "%";
    const COLOR = { ok: "var(--brand)", pace: "#f2b52e", near: "var(--accent)", over: "var(--danger)", none: "var(--line-2)" };
    const GAUGE = { ok: "#8fd0ff", pace: "#ffd25e", near: "#ffa24d", over: "#ff6b6b", none: "#8fd0ff" };
    const SEC_COLORS = ["#004c97", "#2a73c2", "#f47a20", "#0f8a6c", "#6a5fd1", "#f2b52e"];
    const ST = { over: ["Vượt ngân sách", "bad"], near: ["Sắp vượt", "warn"], pace: ["Vượt tiến độ", "bk-pace"], ok: ["Trong mức", "ok"], none: ["Chưa có NS", ""] };
    const badge = (i) => (i.status === "ok" || i.status === "none") && !i.spent ? '<span class="muted">—</span>'
      : `<span class="badge ${ST[i.status][1]}">${ST[i.status][0]}</span>`;
    const lockTag = (i) => (i.blocked ? `<span class="badge bk-lock">${icon("lock")}Đã chặn</span>` : "");
    const bar = (i) => `<div class="bk-bar ${i.status}" title="Đã dùng ${i.percent}% · theo tiến độ năm là ${Math.round(m / 12 * 100)}%"><i style="width:${Math.min(i.percent, 100)}%"></i><u style="left:${m / 12 * 100}%"></u></div>`;
    const why = (i) => (i.status === "over"
      ? `Chi ${bn(i.spent)} / ${bn(i.plan)}: ${i.plan > 0 ? `vượt ${bn(i.over_by)} (${pc(i.percent)} ngân sách)` : "chưa được duyệt ngân sách"}`
      : i.status === "near" ? `Đã dùng ${pc(i.percent)} ngân sách, còn ${bn(i.remaining)}`
      : i.status === "pace" ? `Đã chi ${bn(i.spent)}, cao hơn mức theo tiến độ (${bn(i.expected)} đến T${m})`
      : `Đã chi ${bn(i.spent)} / ${bn(i.plan)} (${pc(i.percent)})`) + (i.blocked ? ". Đang chặn phát sinh thêm chi phí." : "");
    const when = (s) => { const [d, t] = String(s).split(" "); const [, mo, da] = d.split("-"); return `${da}/${mo} ${(t || "").slice(0, 5)}`; };
    const byCode = Object.fromEntries(r.sections.flatMap((s) => s.groups.flatMap((g) => g.lines.map((l) => [l.code, l]))));
    const all = Object.values(byCode);

    // ---- Vòng đo % sử dụng (trên nền xanh) ----
    const R = 62, C = 2 * Math.PI * R, tp = Math.min(T.percent, 100), ex = Math.min(m / 12, 1);
    const ang = ex * 2 * Math.PI - Math.PI / 2;
    const gauge = `<svg viewBox="0 0 160 160" class="bk-gauge" role="img" aria-label="Đã dùng ${pc(T.percent)} ngân sách">
      <circle cx="80" cy="80" r="${R}" class="bk-g-track"/>
      <circle cx="80" cy="80" r="${R}" class="bk-g-arc" stroke="${GAUGE[T.status]}" stroke-dasharray="${(tp / 100) * C} ${C}" transform="rotate(-90 80 80)"/>
      <circle cx="${80 + R * Math.cos(ang)}" cy="${80 + R * Math.sin(ang)}" r="5" class="bk-g-pace"><title>Mức theo tiến độ năm (T${m}/12)</title></circle>
      <text x="80" y="82" text-anchor="middle" class="bk-g-num">${Math.round(T.percent)}%</text>
      <text x="80" y="102" text-anchor="middle" class="bk-g-lbl">đã sử dụng</text></svg>`;

    // ---- Biểu đồ lũy kế: kế hoạch theo tiến độ so với thực chi ----
    const W = 760, pl = 52, pr = 16, pt = 18, iw = W - pl - pr;
    const H1 = 270, pb1 = 26, ih1 = H1 - pt - pb1;
    const ymax = Math.max(T.plan, ...r.monthly.map((x) => x.cum_spent), 1) * 1.08;
    const X = (k) => pl + ((k - 0.5) / 12) * iw, Y = (v) => pt + ih1 - (v / ymax) * ih1;
    const dataMonths = r.monthly.filter((x) => x.has_data);
    const actPts = dataMonths.map((x) => `${X(x.month)},${Y(x.cum_spent)}`);
    const lastD = dataMonths[dataMonths.length - 1];
    const paceUp = lastD && lastD.cum_spent > lastD.cum_plan * 1.0;
    const actColor = lastD && lastD.cum_spent > T.plan ? "var(--danger)" : paceUp ? "var(--accent)" : "var(--brand)";
    const tickV = [0, 1, 2, 3, 4].map((i) => (ymax / 4) * i);
    const chart1 = `<svg viewBox="0 0 ${W} ${H1}" class="bk-chart" role="img" aria-label="Chi lũy kế so với ngân sách theo tiến độ">
      <defs><linearGradient id="bkg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${actColor}" stop-opacity=".35"/><stop offset="1" stop-color="${actColor}" stop-opacity="0"/></linearGradient></defs>
      ${tickV.map((v) => `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" class="bk-grid"/><text x="${pl - 8}" y="${Y(v) + 4}" text-anchor="end" class="bk-ax">${(v / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 0 })}</text>`).join("")}
      <text x="${pl - 8}" y="${pt - 6}" text-anchor="end" class="bk-ax">tỷ</text>
      <line x1="${pl}" x2="${W - pr}" y1="${Y(T.plan)}" y2="${Y(T.plan)}" class="bk-cap"/>
      <text x="${W - pr}" y="${Y(T.plan) - 6}" text-anchor="end" class="bk-cap-t">Ngân sách năm ${bn(T.plan)}</text>
      <line x1="${X(m)}" x2="${X(m)}" y1="${pt}" y2="${pt + ih1}" class="bk-now"/>
      <polyline points="${pl},${Y(0)} ${r.monthly.map((x) => `${X(x.month)},${Y(x.cum_plan)}`).join(" ")}" class="bk-plan-line"/>
      ${actPts.length ? `<polygon points="${X(dataMonths[0].month)},${Y(0)} ${actPts.join(" ")} ${X(lastD.month)},${Y(0)}" fill="url(#bkg)"/>
        <polyline points="${actPts.join(" ")}" class="bk-act-line" stroke="${actColor}"/>
        ${dataMonths.map((x) => `<circle cx="${X(x.month)}" cy="${Y(x.cum_spent)}" r="3.5" fill="#fff" stroke="${actColor}" stroke-width="2"/>`).join("")}` : ""}
      ${r.monthly.map((x) => `<rect x="${pl + ((x.month - 1) / 12) * iw}" y="${pt}" width="${iw / 12}" height="${ih1}" class="bk-hit"><title>Tháng ${x.month}
Kế hoạch lũy kế: ${bn(x.cum_plan)}
Thực chi lũy kế: ${x.has_data ? bn(x.cum_spent) : "chưa có số"}</title></rect>
        <text x="${X(x.month)}" y="${H1 - 8}" text-anchor="middle" class="bk-ax ${x.month === m ? "on" : ""}">T${x.month}</text>`).join("")}</svg>`;

    // ---- Chi theo tháng ----
    const H2 = 130, pb2 = 24, ih2 = H2 - 22 - pb2, avg = T.plan / 12;
    const bmax = Math.max(avg, ...r.monthly.map((x) => x.spent)) * 1.15 || 1;
    const chart2 = `<svg viewBox="0 0 ${W} ${H2}" class="bk-chart" role="img" aria-label="Chi thực tế theo tháng">
      ${r.monthly.map((x) => {
        const h = (x.spent / bmax) * ih2, over = x.spent > avg;
        return `<g><title>Tháng ${x.month}: chi ${bn(x.spent)}${over ? " (cao hơn bình quân kế hoạch)" : ""}</title>
          <rect x="${X(x.month) - iw / 12 * 0.3}" y="${22 + ih2 - h}" width="${iw / 12 * 0.6}" height="${Math.max(h, x.has_data ? 1.5 : 0)}" rx="5" fill="${over ? "var(--accent)" : "var(--brand)"}" opacity="${x.has_data ? 1 : 0.15}"/>
          ${x.has_data && x.spent ? `<text x="${X(x.month)}" y="${22 + ih2 - h - 5}" text-anchor="middle" class="bk-val">${bn(x.spent).replace(" ", " ")}</text>` : ""}
          <text x="${X(x.month)}" y="${H2 - 7}" text-anchor="middle" class="bk-ax ${x.month === m ? "on" : ""}">T${x.month}</text></g>`;
      }).join("")}
      <line x1="${pl}" x2="${W - pr}" y1="${22 + ih2 - (avg / bmax) * ih2}" y2="${22 + ih2 - (avg / bmax) * ih2}" class="bk-avg"/>
      <text x="${pl}" y="12" class="bk-ax">Chi theo tháng · vạch đỏ: bình quân kế hoạch ${bn(avg)}/tháng</text></svg>`;

    // ---- Cơ cấu ngân sách theo nhóm (vòng tròn) ----
    const DR = 66, DC = 2 * Math.PI * DR, totalPlan = r.sections.reduce((a, s) => a + s.plan, 0) || 1;
    let acc = 0;
    const donut = `<svg viewBox="0 0 180 180" class="bk-donut" role="img" aria-label="Cơ cấu ngân sách theo nhóm chi phí">
      ${r.sections.map((s, k) => {
        const len = Math.max((s.plan / totalPlan) * DC - 2, 0.5), seg = `<circle cx="90" cy="90" r="${DR}" fill="none" stroke="${SEC_COLORS[k % SEC_COLORS.length]}" stroke-width="26" stroke-dasharray="${len} ${DC}" stroke-dashoffset="${-acc}" transform="rotate(-90 90 90)" class="bk-seg" data-secf="${esc(s.name)}"><title>${esc(s.name)}: ${bn(s.plan)} (${pc(s.plan / totalPlan * 100)})</title></circle>`;
        acc += (s.plan / totalPlan) * DC;
        return seg;
      }).join("")}
      <text x="90" y="86" text-anchor="middle" class="bk-d-num">${bn(totalPlan)}</text><text x="90" y="104" text-anchor="middle" class="bk-ax">ngân sách năm</text></svg>`;

    // ---- Hạng mục dùng nhiều nhất (hoặc lớn nhất khi chưa có số chi) ----
    const used = all.filter((i) => i.plan > 0 && i.spent > 0).sort((a, b) => b.percent - a.percent).slice(0, 8);
    const biggest = [...all].sort((a, b) => b.plan - a.plan).slice(0, 8);
    const meter = (i) => { const mx = Math.max(120, i.percent); return `<div class="bk-meter" title="${pc(i.percent)}"><i style="width:${Math.min(i.percent, mx) / mx * 100}%;background:${COLOR[i.status]}"></i><u style="left:${80 / mx * 100}%"></u><u class="r" style="left:${100 / mx * 100}%"></u></div>`; };
    const topList = used.length
      ? used.map((i) => `<li><div class="bk-top-h"><span title="${esc(i.name)}">${esc(i.name)}</span><b style="color:${COLOR[i.status]}">${pc(i.percent)}</b></div>${meter(i)}</li>`).join("")
      : biggest.map((i) => `<li><div class="bk-top-h"><span title="${esc(i.name)}">${esc(i.name)}</span><b>${bn(i.plan)}</b></div><div class="bk-meter"><i style="width:${i.plan / biggest[0].plan * 100}%;background:var(--brand-400)"></i></div></li>`).join("");

    // ---- Cần xử lý ----
    const alerts = r.alerts;
    const alertHtml = alerts.length ? alerts.map((i) => `
      <div class="bk-alert ${i.status} ${i.blocked ? "blocked" : ""}">
        <div class="bk-alert-main">
          <div class="bk-tags">${i.status === "over" || i.status === "near" || i.status === "pace" ? `<span class="badge ${ST[i.status][1]}">${ST[i.status][0]}</span>` : ""}${lockTag(i)}${i.supplement ? `<span class="badge brand">+${bn(i.supplement)} đã duyệt</span>` : ""}</div>
          <b>${esc(i.name)}</b>
          <small class="muted">${esc(i.code)} · ${esc(i.section)}</small>
          ${meter(i)}
          <p>${esc(why(i))}</p></div>
        <div class="bk-alert-act">
          ${i.status === "over" || i.status === "near" || i.blocked ? `<button class="bk-btn supp" data-act="supp" data-code="${esc(i.code)}">${icon("plus")}Duyệt bổ sung</button>` : ""}
          ${i.blocked ? `<button class="bk-btn go" data-act="unblock" data-code="${esc(i.code)}">${icon("check")}Cho tiếp tục</button>`
            : `<button class="bk-btn stop" data-act="block" data-code="${esc(i.code)}">${icon("lock")}Chặn phát sinh</button>`}
          <button class="bk-btn quiet" data-act="edit" data-code="${esc(i.code)}" title="Nhập chi thực tế">${icon("edit")}</button></div></div>`).join("")
      : `<div class="empty">${r.last_data_month ? "Chưa có hạng mục nào vượt, sắp vượt hoặc bị chặn." : "Chưa có số chi thực tế nên chưa có cảnh báo."}</div>`;
    const KIND = { supplement: ["Duyệt bổ sung", "k-supp"], block: ["Chặn phát sinh", "k-stop"], unblock: ["Cho tiếp tục", "k-go"] };
    const log = r.decisions.length ? `<ul class="bk-log">${r.decisions.map((d) => `<li class="${KIND[d.kind][1]}"><span class="dot"></span><div>
        <b>${KIND[d.kind][0]}${d.amount ? ` ${bn(d.amount)}` : ""}</b> · ${esc(d.name || d.code)}
        <small>${d.note ? esc(d.note) + " · " : ""}${esc(d.by_name || "—")} · ${when(d.decided_at)}</small></div></li>`).join("")}</ul>`
      : '<div class="empty">Chưa có quyết định nào.</div>';

    main.innerHTML = `<div id="bk-root">
      <section class="bk-hero">
        <div class="bk-hero-top">
          <div><span class="bk-eyebrow">Ngân sách hoạt động</span><h2>Năm ${r.year}</h2>
            <p>Lũy kế đến tháng ${m} so với ngân sách tổng duyệt${T.supplement ? ` (đã gồm ${bn(T.supplement)} TGĐ duyệt bổ sung)` : ""}. Vàng từ ${r.warn_pct}%, đỏ khi vượt 100%.</p></div>
          <div class="bk-actions">
            <select id="bk-month" class="bk-glass" aria-label="Chi lũy kế đến tháng">${[...Array(12)].map((_, k) => `<option value="${k + 1}" ${k + 1 === m ? "selected" : ""}>Đến tháng ${k + 1}</option>`).join("")}</select>
            <a class="bk-glass" href="/api/budget/actuals/template" download>${icon("download")}File mẫu</a>
            <a class="bk-glass" href="/api/budget/export?month=${m}" download>${icon("file")}Xuất Excel</a>
            <button class="bk-glass" id="bk-print">${icon("file")}In / PDF</button>
            <button class="bk-glass" id="bk-act">${icon("upload")}Nhập chi thực tế</button>
            <button class="bk-glass" id="bk-plan">${icon("file")}Cập nhật kế hoạch</button></div></div>
        <div class="bk-hero-body">
          ${gauge}
          <div class="bk-hero-nums">
            <div><span>Ngân sách hiệu lực</span><b>${bn(T.plan)}</b><small>Bình quân ${bn(T.plan / 12)}/tháng</small></div>
            <div><span>Đã chi lũy kế (T1–T${m})</span><b>${bn(T.spent)}</b><small>Theo tiến độ năm là ${bn(T.expected)}</small></div>
            <div><span>Còn lại</span><b class="${T.remaining < 0 ? "neg" : ""}">${bn(T.remaining)}</b><small>${Math.max(0, 12 - m)} tháng còn lại trong năm</small></div></div>
          <div class="bk-chips">
            <span class="bk-chip over ${T.over ? "" : "zero"}"><b>${T.over}</b>Vượt ngân sách</span>
            <span class="bk-chip near ${T.near ? "" : "zero"}"><b>${T.near}</b>Sắp vượt</span>
            <span class="bk-chip pace ${T.pace ? "" : "zero"}"><b>${T.pace}</b>Vượt tiến độ</span>
            <span class="bk-chip lock ${T.blocked ? "" : "zero"}"><b>${T.blocked}</b>Đang bị chặn</span></div></div>
        ${r.last_data_month ? "" : `<div class="bk-cta"><div><b>Chưa có số chi thực tế</b><span>Tải file mẫu, điền chi theo tháng rồi nhập vào để bắt đầu theo dõi và nhận cảnh báo. Cũng có thể bấm biểu tượng bút ở từng hạng mục bên dưới.</span></div>
          <a class="bk-cta-btn ghost" href="/api/budget/actuals/template" download>${icon("download")}Tải file mẫu</a>
          <button class="bk-cta-btn" id="bk-cta-act">${icon("upload")}Nhập chi thực tế</button></div>`}
      </section>
      <div class="bk-grid-2">
        <div class="card"><div class="card-head"><h3><span class="ico-chip">${icon("chart")}</span>Chi lũy kế so với ngân sách<span class="sub">Đường nét đứt là mức chi nếu đi đúng tiến độ năm</span></h3>
          <div class="bk-legend"><span><i style="background:${actColor}"></i>Thực chi</span><span><i class="dash"></i>Theo tiến độ</span></div></div>
          ${chart1}${r.last_data_month ? chart2 : ""}</div>
        <div class="card"><div class="card-head"><h3><span class="ico-chip">${icon("layers")}</span>Cơ cấu ngân sách<span class="sub">Theo nhóm chi phí, kèm mức đã dùng</span></h3></div>
          ${donut}
          <ul class="bk-donut-legend">${r.sections.map((s, k) => `<li class="bk-dl ${state.bkSection === s.name ? "on" : ""}" data-secf="${esc(s.name)}" title="Bấm để chỉ xem nhóm này trong bảng chi tiết"><span class="sw" style="background:${SEC_COLORS[k % SEC_COLORS.length]}"></span>
            <div><div class="bk-dl-h"><span>${esc(s.name)}</span><b style="color:${COLOR[s.status]}">${pc(s.percent)}</b></div>
            <small class="muted">${bn(s.spent)} / ${bn(s.plan)} · ${pc(s.plan / totalPlan * 100)} tổng ngân sách</small>${bar(s)}</div></li>`).join("")}</ul></div>
      </div>
      <div class="bk-grid-3">
        <div class="card"><div class="card-head"><h3><span class="ico-chip">${icon("alert")}</span>Cần xử lý<span class="sub">Tổng Giám đốc duyệt bổ sung hoặc chặn không cho phát sinh thêm</span></h3></div>
          <div class="bk-alerts">${alertHtml}</div></div>
        <div class="bk-side">
          <div class="card"><div class="card-head"><h3><span class="ico-chip">${icon("target")}</span>${used.length ? "Mức sử dụng cao nhất" : "Hạng mục lớn nhất"}</h3></div>
            <ul class="bk-top">${topList}</ul>${used.length ? '<p class="muted bk-note"><u class="a"></u>80% <u class="b"></u>100% ngân sách</p>' : ""}</div>
          <div class="card"><div class="card-head"><h3><span class="ico-chip">${icon("shield")}</span>Quyết định gần đây</h3></div>${log}</div></div>
      </div>
      <div class="card">
        <div class="toolbar bk-toolbar"><h3 style="margin:0">Chi tiết theo hạng mục <span class="muted" style="font-weight:400;font-size:13px">(triệu đồng)</span> <span id="bk-secchip"></span></h3>
          <div class="btn-group"><input type="search" id="bk-q" class="pill-select" style="min-width:260px" placeholder="Tìm mã hoặc tên hạng mục..." value="${esc(state.bkQuery || "")}">
            <select id="bk-filter" class="pill-select">${[["", "Tất cả hạng mục"], ["alert", "Có cảnh báo"], ["over", "Chỉ vượt ngân sách"], ["near", "Chỉ sắp vượt"], ["blocked", "Đang bị chặn"], ["spent", "Đã có chi"]]
              .map(([v, l]) => `<option value="${v}" ${v === (state.bkFilter || "") ? "selected" : ""}>${l}</option>`).join("")}</select></div></div>
        <div class="bk-scroll"><table class="bk-table"><thead><tr><th>Hạng mục</th><th class="num">Ngân sách</th><th class="num">Đã chi</th><th class="num">Còn lại</th><th style="width:150px">Mức sử dụng</th><th>Trạng thái</th><th></th></tr></thead>
        <tbody id="bk-body"></tbody></table></div>
      </div></div>`;

    const plain = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();
    if (!state.bkOpen) state.bkOpen = new Set(r.sections.filter((s) => s.over + s.near + s.pace + s.blocked > 0).map((s) => s.name));
    const drawBody = () => {
      const q = plain(state.bkQuery || "").trim(), f = state.bkFilter || "";
      const pass = (i) => (!q || plain(i.code + " " + i.name).includes(q))
        && (!f || (f === "alert" ? ["over", "near", "pace"].includes(i.status) : f === "spent" ? i.spent > 0 : f === "blocked" ? i.blocked : i.status === f));
      const forced = !!(q || f || state.bkSection || state.bkPrintOpen);
      let html = "";
      for (const s of r.sections) {
        if (state.bkSection && s.name !== state.bkSection) continue;
        const groups = s.groups.map((g) => ({ g, lines: g.lines.filter(pass) })).filter((x) => x.lines.length);
        if (!groups.length) continue;
        const open = forced || state.bkOpen.has(s.name);
        html += `<tr class="bk-sec" data-sec="${esc(s.name)}"><td><span class="bk-caret ${open ? "open" : ""}">${icon("chev")}</span><b>${esc(s.name)}</b></td>
          <td class="num">${tr(s.plan)}</td><td class="num">${tr(s.spent)}</td><td class="num ${s.remaining < 0 ? "neg" : ""}">${tr(s.remaining)}</td><td>${bar(s)}</td><td>${badge(s)}</td><td></td></tr>`;
        if (!open) continue;
        for (const { g, lines } of groups) {
          if (g.name) html += `<tr class="bk-grp"><td>${esc(g.name)}</td><td class="num">${tr(g.plan)}</td><td class="num">${tr(g.spent)}</td><td class="num ${g.remaining < 0 ? "neg" : ""}">${tr(g.remaining)}</td><td></td><td></td><td></td></tr>`;
          html += lines.map((i) => `<tr class="bk-line ${i.status}"><td><span class="bk-code">${esc(i.code)}</span>${esc(i.name)} ${lockTag(i)}${i.note ? `<small class="muted">${esc(i.note)}</small>` : ""}</td>
            <td class="num" title="${dong(i.plan)}${i.supplement ? ` (gốc ${dong(i.base_plan)} + bổ sung ${dong(i.supplement)})` : ""}">${tr(i.plan)}${i.supplement ? `<small class="bk-plus">+${tr(i.supplement)}</small>` : ""}</td><td class="num" title="${dong(i.spent)}">${tr(i.spent)}</td>
            <td class="num ${i.remaining < 0 ? "neg" : ""}">${i.plan || i.spent ? tr(i.remaining) : "—"}</td><td>${i.plan || i.spent ? bar(i) : ""}</td><td>${badge(i)}</td>
            <td class="bk-row-act"><button class="icon-btn" data-act="edit" data-code="${esc(i.code)}" title="Nhập chi thực tế" aria-label="Nhập chi thực tế ${esc(i.code)}">${icon("edit")}</button>
              <button class="icon-btn" data-act="menu" data-code="${esc(i.code)}" title="Duyệt bổ sung / chặn phát sinh" aria-label="Quyết định ngân sách ${esc(i.code)}">${icon("shield")}</button></td></tr>`).join("");
        }
      }
      $("#bk-secchip").innerHTML = state.bkSection ? `<button class="bk-secchip" data-secf="" title="Bỏ lọc nhóm">${esc(state.bkSection)} ${icon("plus")}</button>` : "";
      document.querySelectorAll("#bk-root .bk-dl").forEach((li) => li.classList.toggle("on", li.dataset.secf === state.bkSection));
      $("#bk-body").innerHTML = html || '<tr><td colspan="7"><div class="empty">Không có hạng mục nào khớp.</div></td></tr>';
      hydrateIcons($("#bk-body"));
    };
    drawBody();

    const editLine = (code) => {
      const i = byCode[code];
      if (!i) return;
      openForm(`Chi thực tế · ${i.code}`, [
        { type: "info", label: `${i.name}. Ngân sách ${dong(i.plan)}; đã chi lũy kế đến T${m}: ${dong(i.spent)}. Nhập số tiền (đồng) của từng tháng; để trống là chưa có số.${i.blocked ? " Hạng mục đang bị chặn: chỉ sửa giảm được, không ghi thêm chi." : ""}` },
        ...i.months.map((_, k) => ({ name: `m${k + 1}`, label: `Tháng ${k + 1}`, type: "number", placeholder: "0" })),
      ], Object.fromEntries(i.months.map((v, k) => [`m${k + 1}`, v])), async (d) => {
        const months = Object.fromEntries(i.months.map((_, k) => [String(k + 1), d[`m${k + 1}`] === "" || d[`m${k + 1}`] == null ? null : Number(d[`m${k + 1}`])]));
        await api(`/api/budget/lines/${encodeURIComponent(code)}/actuals`, { method: "PUT", body: { months } });
        toast("Đã lưu số chi thực tế");  // openForm tự vẽ lại trang sau khi lưu
      });
    };
    const decision = (code, body) => api(`/api/budget/lines/${encodeURIComponent(code)}/decision`, { method: "POST", body });
    const supplement = (code) => {
      const i = byCode[code];
      const hint = i.over_by > 0 ? Math.ceil(i.over_by / 1e6) * 1e6 : "";
      openForm(`Duyệt bổ sung ngân sách · ${i.code}`, [
        { type: "info", label: `${i.name}. Ngân sách hiện tại ${dong(i.plan)}, đã chi ${dong(i.spent)}${i.over_by > 0 ? `, đang vượt ${dong(i.over_by)}` : ""}. Số tiền duyệt được cộng thẳng vào ngân sách của hạng mục này${i.blocked ? " và hạng mục được gỡ chặn" : ""}.` },
        { name: "amount", label: "Số tiền bổ sung (đồng)", type: "number", required: true, placeholder: i.over_by > 0 ? "Gợi ý: đủ bù phần đang vượt" : "" },
        { name: "note", label: "Lý do duyệt (bắt buộc)", type: "textarea", required: true, placeholder: "Ví dụ: giá xăng tăng, phát sinh sự kiện..." },
      ], { amount: hint }, async (d) => {
        await decision(code, { kind: "supplement", amount: d.amount, note: d.note });
        toast(`Đã duyệt bổ sung ${bn(d.amount)} cho ${i.code}`);
      }, "Duyệt bổ sung");
    };
    const block = (code) => {
      const i = byCode[code];
      openForm(`Chặn phát sinh · ${i.code}`, [
        { type: "info", label: `${i.name}. Sau khi chặn, hệ thống không cho ghi thêm chi phí cho hạng mục này (chỉ cho sửa giảm), cho đến khi TGĐ duyệt bổ sung hoặc cho tiếp tục.` },
        { name: "note", label: "Lý do chặn (không bắt buộc)", type: "textarea" },
      ], {}, async (d) => { await decision(code, { kind: "block", note: d.note }); toast(`Đã chặn phát sinh ${i.code}`); }, "Chặn phát sinh");
    };
    const unblock = async (code) => {
      const i = byCode[code];
      if (!(await ask({ title: `Cho ${i.code} tiếp tục phát sinh?`, message: `${i.name}. Hạng mục được ghi thêm chi phí trở lại, kể cả khi đã vượt ngân sách.`, okText: "Cho tiếp tục" }))) return;
      try { await decision(code, { kind: "unblock", note: "Cho tiếp tục" }); toast(`Đã cho ${i.code} tiếp tục`); render(); } catch (e) { toast(e.message, "err"); }
    };
    const menu = async (code) => {
      const i = byCode[code];
      const pick = await askChoice({ title: `${i.code} · ${i.name}`, message: "Quyết định của Tổng Giám đốc với hạng mục này:", options: [
        { label: "Duyệt bổ sung ngân sách", value: "supp", primary: true },
        i.blocked ? { label: "Cho tiếp tục phát sinh", value: "unblock" } : { label: "Chặn phát sinh", value: "block", danger: true },
        { label: "Đóng", value: null }] });
      if (pick === "supp") supplement(code); else if (pick === "block") block(code); else if (pick === "unblock") unblock(code);
    };
    const ACTS = { edit: editLine, supp: supplement, block, unblock, menu };
    $("#bk-root").onclick = (e) => {
      const sf = e.target.closest("[data-secf]");
      if (sf) {  // bấm nhóm trong biểu đồ vòng: bảng chi tiết chỉ hiện nhóm đó; bấm lại hoặc bấm chip để bỏ lọc
        const n = sf.dataset.secf;
        state.bkSection = !n || n === state.bkSection ? null : n;
        drawBody();
        if (state.bkSection) $("#bk-body").closest(".card").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      const b = e.target.closest("[data-act]");
      if (b) return ACTS[b.dataset.act]?.(b.dataset.code);
      const sec = e.target.closest(".bk-sec");
      if (sec) { const n = sec.dataset.sec; state.bkOpen.has(n) ? state.bkOpen.delete(n) : state.bkOpen.add(n); drawBody(); }
    };
    $("#bk-q").oninput = (e) => { state.bkQuery = e.target.value; drawBody(); };
    $("#bk-filter").onchange = (e) => { state.bkFilter = e.target.value; drawBody(); };
    $("#bk-month").onchange = (e) => { state.bkMonth = Number(e.target.value); VIEWS.budget(main); };
    $("#bk-plan").onclick = importPlan;
    $("#bk-print").onclick = () => window.print();
    // In / lưu PDF: mở hết các nhóm trong bảng để báo cáo đủ hạng mục, in xong trả lại như cũ
    state.bkPrint = { before: () => { state.bkPrintOpen = true; drawBody(); }, after: () => { state.bkPrintOpen = false; drawBody(); } };
    const pickActuals = () => pickFile(".xlsx,.xlsm,.csv", "/api/budget/actuals/import", (res) => {
      const skipped = [res.unknown.length ? `mã không có trong kế hoạch: ${res.unknown.slice(0, 5).join(", ")}` : "", res.blocked.length ? `hạng mục đang bị chặn: ${res.blocked.slice(0, 5).join(", ")}` : ""].filter(Boolean);
      toast(`Đã nhập ${res.entries} ô số chi của ${res.lines} hạng mục.` + (skipped.length ? ` Bỏ qua ${skipped.join("; ")}.` : ""), skipped.length ? "err" : "ok");
      state.bkMonth = null;
      VIEWS.budget(main);
    });
    $("#bk-act").onclick = pickActuals;
    if ($("#bk-cta-act")) $("#bk-cta-act").onclick = pickActuals;
  },

  async aicost(main) {
    const days = state.aicostDays || 7;
    const r = await api(`/api/ai/cost?days=${days}`);
    // Kiểu của trang thanh toán Anthropic: 2 số lẻ, dấu phẩy thập phân, hậu tố US$; dưới 1 cent hiện "< 0,01 US$"
    const usd = (n) => {
      n = Number(n || 0);
      return n > 0 && n < 0.01 ? "< 0,01 US$" : n.toLocaleString("vi-VN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " US$";
    };
    const KIND = { chat: "Chat với trợ lý", ocr_pdf: "Đọc PDF scan (OCR)", ocr_image: "Đọc ảnh (OCR)", verify_scan: "Đối chiếu bản scan",
      web_summary: "Tóm tắt trang web", memory: "Ghi chú / việc nền" };
    const max = Math.max(0.0001, ...r.daily.map((d) => d.cost_usd));
    const limitNote = r.daily_limit_usd > 0 ? `Trần công ty ${usd(r.daily_limit_usd)}/ngày` : "Không đặt trần công ty";
    main.innerHTML = `
      <div class="card">
        <div class="toolbar"><h3 style="margin:0">Chi phí AI</h3>
          <select id="aic-days" class="pill-select">${[7, 14, 30, 90].map((n) => `<option value="${n}" ${n === days ? "selected" : ""}>${n} ngày gần nhất</option>`).join("")}</select></div>
        <p class="muted">Số tiền là ước tính theo bảng giá trong hệ thống, không phải hóa đơn của nhà cung cấp. Trần reset lúc 0 giờ mỗi ngày.</p>
        ${r.credit ? `<div class="credit-box"><div class="stat-row">
            <div><b>${usd(r.credit.remaining_usd)}</b><span>Số dư còn lại (ước tính)</span></div>
            <div><b>${usd(r.credit.used_usd)}</b><span>Đã dùng${r.credit.since ? " từ " + esc(r.credit.since) : " toàn bộ từ trước đến nay"}</span></div>
            <div><b>${usd(r.credit.total_usd)}</b><span>Đã nạp</span></div></div>
          <div class="quota-bar ${r.credit.percent_used >= 100 ? "full" : r.credit.percent_used >= 80 ? "warn" : ""}"><i style="width:${r.credit.percent_used}%"></i></div>
          <p class="muted">${r.credit.percent_used}% số tiền đã nạp đã dùng${r.credit.remaining_usd <= 0 ? " — đã hết, hãy nạp thêm ở console.anthropic.com" : ""}. Số dư thật xem ở console.anthropic.com.</p></div>`
          : `<p class="muted">Muốn xem số dư còn lại, đặt AZB_CREDIT_USD (số tiền đã nạp, ví dụ 20) trong file .env rồi khởi động lại.</p>`}
        <div class="stat-row">
          <div><b>${usd(r.today_usd)}</b><span>Hôm nay · ${limitNote}</span></div>
          <div><b>${usd(r.total_usd)}</b><span>Tổng ${r.days} ngày</span></div>
          <div><b>${usd(r.total_usd / r.days)}</b><span>Trung bình mỗi ngày</span></div>
          <div><b>${usd(r.all_time.cost_usd)}</b><span>Tổng đã dùng${r.all_time.since ? " từ " + esc(r.all_time.since) : ""} · ${fmtNum(r.all_time.calls)} lượt · ${fmtNum(r.all_time.input_tokens)} token vào · ${fmtNum(r.all_time.output_tokens)} token ra</span></div>
        </div>
      </div>
      <div class="card"><h3>Theo ngày</h3>
        ${r.daily.length ? `<table><tr><th>Ngày</th><th class="num">Lượt gọi</th><th class="num">Token vào</th><th class="num">Token ra</th><th class="num">Chi phí</th><th style="width:30%"></th></tr>
          ${r.daily.map((d) => `<tr><td>${esc(d.day)}</td><td class="num">${fmtNum(d.calls)}</td><td class="num">${fmtNum(d.input_tokens)}</td>
            <td class="num">${fmtNum(d.output_tokens)}</td><td class="num">${usd(d.cost_usd)}</td>
            <td><div class="quota-bar"><i style="width:${Math.round((d.cost_usd / max) * 100)}%"></i></div></td></tr>`).join("")}</table>`
          : '<div class="empty">Chưa có lượt gọi AI nào trong khoảng này.</div>'}
      </div>
      <div class="card"><h3>Theo người dùng</h3>
        ${r.by_user.length ? `<table><tr><th>Người dùng</th><th class="num">Lượt gọi</th><th class="num">Chi phí</th></tr>
          ${r.by_user.map((u) => `<tr><td>${esc(u.name)}</td><td class="num">${fmtNum(u.calls)}</td><td class="num">${usd(u.cost_usd)}</td></tr>`).join("")}</table>`
          : '<div class="empty">Chưa có dữ liệu.</div>'}
      </div>
      <div class="card"><h3>Theo loại việc và model</h3>
        ${r.by_kind.length ? `<table><tr><th>Loại việc</th><th>Model</th><th class="num">Lượt gọi</th><th class="num">Chi phí</th></tr>
          ${r.by_kind.map((k) => `<tr><td>${esc(KIND[k.kind] || k.kind)}</td><td class="muted">${esc(k.model || "—")}</td>
            <td class="num">${fmtNum(k.calls)}</td><td class="num">${usd(k.cost_usd)}</td></tr>`).join("")}</table>`
          : '<div class="empty">Chưa có dữ liệu.</div>'}
      </div>`;
    $("#aic-days").onchange = (e) => { state.aicostDays = Number(e.target.value); VIEWS.aicost(main); };
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
    state.quota = (await api("/api/ai/quota").catch(() => null))?.quota ?? null;
    main.innerHTML = `
      <div class="cg ${(state.chatSidebar ?? !matchMedia("(max-width: 960px)").matches) ? "" : "side-closed"}" id="cg">
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
              ${ai.models?.length ? `<div class="cg-pick" id="cg-pick">
                <button type="button" class="cg-pick-btn" id="cg-pick-btn" aria-haspopup="listbox" aria-expanded="false" title="Chọn model để trả lời">
                  <span id="cg-pick-label"></span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
                </button>
                <div class="cg-pick-menu" id="cg-pick-menu" role="listbox" hidden>
                  <div class="cg-pick-head">Model trả lời</div>
                  ${ai.models.map((m) => `<button type="button" role="option" class="cg-pick-opt" data-id="${esc(m.id)}">
                    <span class="mt"><b>${esc(modelName(m.label))}</b><small>${esc(m.hint)}</small></span>
                    <svg class="ck" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5L20 7"/></svg>
                  </button>`).join("")}
                </div>
              </div>` : ""}
              <button class="cg-send" id="send" type="submit" title="Gửi (Enter)">↑</button>
            </form>
            <div class="cg-meter" id="cg-meter"></div>
            <div class="cg-quota" id="cg-quota"></div>
            <div class="cg-hint">Enter để gửi · Shift+Enter xuống dòng · AI có thể sai, hãy kiểm tra lại số liệu quan trọng</div>
          </div>
        </section>
      </div>`;

    const log = $("#log"), q = $("#q");
    drawAiMeter();
    // Chọn model: menu tuỳ biến (thay cho <select> gốc), nhớ lựa chọn trên trình duyệt này
    let chatModel = null;
    let modelLocked = false;  // đã chọn model (ở ô chọn hoặc trả lời hộp hỏi nâng model) trong đoạn chat này: không hỏi nâng nữa
    let closeAsk = null;      // đóng hộp hỏi nâng model đang hiện (coi như huỷ gửi)
    let resetModel = () => {};  // đoạn chat mới: về lại model mặc định của người dùng
    let showModel = () => {};  // mở lại đoạn chat cũ: hiện đúng model đã trả lời đoạn đó
    if ($("#cg-pick")) {
      let saved = null;
      try { saved = localStorage.getItem("azb_chat_model"); } catch {}
      const ids = ai.models.map((m) => m.id);
      chatModel = ids.includes(saved) ? saved : ids.includes(ai.default_model) ? ai.default_model : ids[0];
      let baseModel = chatModel;  // model người dùng đã chọn làm thói quen; đoạn chat mới bắt đầu từ đây (nâng model trong một đoạn chat không đổi nó)
      resetModel = () => { chatModel = baseModel; paint(); };
      const pick = $("#cg-pick"), btn = $("#cg-pick-btn"), menu = $("#cg-pick-menu");
      const paint = () => {
        $("#cg-pick-label").textContent = modelName(ai.models.find((m) => m.id === chatModel).label);
        menu.querySelectorAll(".cg-pick-opt").forEach((o) => o.setAttribute("aria-selected", String(o.dataset.id === chatModel)));
      };
      showModel = (id) => { if (ids.includes(id)) { chatModel = id; paint(); } };
      const setOpen = (on) => { menu.hidden = !on; btn.setAttribute("aria-expanded", String(on)); pick.classList.toggle("open", on); };
      btn.onclick = () => setOpen(menu.hidden);
      menu.querySelectorAll(".cg-pick-opt").forEach((o) => (o.onclick = () => {
        chatModel = baseModel = o.dataset.id;
        modelLocked = true;
        try { localStorage.setItem("azb_chat_model", chatModel); } catch {}
        paint();
        setOpen(false);
        $("#q")?.focus();
      }));
      document.addEventListener("click", (e) => { if (!pick.isConnected) return; if (!pick.contains(e.target)) setOpen(false); });
      pick.addEventListener("keydown", (e) => { if (e.key === "Escape") { setOpen(false); btn.focus(); e.stopPropagation(); } });
      paint();
    }
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
          <div class="cg-logo">${icon("spark")}</div>
          <h2>Xin chào ${esc(name)}, hôm nay cần nắm thông tin gì?</h2>
          <p class="muted">Hỏi về tổ chức, nhân sự, quy trình, tài liệu, mục tiêu. Trợ lý tra cứu trực tiếp dữ liệu công ty.</p>
          <div class="cg-suggest">${CHAT_SUGGESTIONS.map((s) => `<button>${esc(s)}</button>`).join("")}</div>
        </div>`;
      log.querySelectorAll(".cg-suggest button").forEach((b) => (b.onclick = () => send(b.textContent)));
    };
    const scroll = () => (log.scrollTop = log.scrollHeight);
    const pendingHtml = (job) => msgHtml({ role: "user", content: job.text }) + `<div class="msg assistant pending" id="pending"><div class="av">AZB</div>
        <div class="body"><span class="dots"><i></i><i></i><i></i></span> <span class="prog">${job.progress ? "Đang tra cứu: " + esc(job.progress) + "…" : "Đang tra cứu dữ liệu và phân tích..."}</span> <span class="esc-hint muted">· nhấn Esc để dừng</span><div class="live">${job.partial ? partialHtml(job.partial) : ""}</div></div></div>`;
    const setProgress = (job) => {
      const el = document.querySelector("#pending .prog");
      if (el) el.textContent = `Đang tra cứu: ${job.progress}…`;
    };
    // Chữ AI đang viết (máy chủ đã lọc ảnh/link, che SĐT/email); câu trả lời cuối thay thế bản này khi xong
    const partialHtml = (text) => (window.marked ? marked.parse(esc(text).replace(/&gt;/g, ">")) : esc(text));
    const setPartial = (job) => {
      const el = document.querySelector("#pending .live");
      if (!el || state.chatJob !== job.token) return;
      const stick = log.scrollHeight - log.scrollTop - log.clientHeight < 120;
      el.innerHTML = job.partial ? partialHtml(job.partial) : "";
      if (stick) scroll();
    };
    // Gửi câu hỏi theo luồng SSE: cập nhật tiến trình khi AI gọi công cụ; trả về đúng kết quả như /api/chat
    const serverErr = (msg) => Object.assign(new Error(msg), { server: true });
    const readStream = async (job, body, ctrl) => {
      const r = await fetch("/api/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: ctrl.signal });
      if (r.status === 401) {
        boot();
        throw serverErr("Phiên đăng nhập đã hết hạn");
      }
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw serverErr(typeof err.detail === "string" ? err.detail : `Lỗi máy chủ (${r.status})`);
      }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "", final = null;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const line = buf.slice(0, i).trim();
          buf = buf.slice(i + 2);
          if (!line.startsWith("data:")) continue;  // dòng ": ping" giữ kết nối
          const ev = JSON.parse(line.slice(5));
          if (ev.type === "tool") {
            job.progress = TOOL_LABELS[ev.tool] || "dữ liệu công ty";
            setProgress(job);
          } else if (ev.type === "text") {
            job.partial = ev.text;
            setPartial(job);
          } else if (ev.type === "done") final = ev;
          else if (ev.type === "error") throw serverErr(ev.detail);
        }
      }
      if (!final) throw new Error("Mất kết nối khi đang trả lời.");
      return final;
    };
    // Trình duyệt di động cắt kết nối khi người dùng rời app, nhưng máy chủ vẫn trả lời xong và lưu vào đoạn chat:
    // lấy lại câu trả lời đã lưu thay vì báo lỗi (để người dùng không phải hỏi lại, tốn thêm hạn mức)
    const recoverAnswer = async (job) => {
      const base = await job.base;  // số tin của đoạn chat trước khi gửi (null: đoạn chat mới hoặc không đọc được)
      for (let i = 0; i < 75 && !job.cancelled; i++) {  // tối đa ~5 phút
        const prog = document.querySelector("#pending .prog");
        if (prog && currentJob() === job) prog.textContent = "Mất kết nối (có thể do rời app). Câu trả lời vẫn được lưu, đang lấy lại…";
        try {
          const convId = job.convId ?? (await api("/api/conversations")).find((c) => !job.baseIds.has(c.id))?.id;
          if (convId != null) {
            const msgs = (await api(`/api/conversations/${convId}`)).messages;
            const last = msgs[msgs.length - 1], asked = msgs[msgs.length - 2];
            const saved = job.convId == null || (base != null ? msgs.length >= base + 2
              : asked?.role === "user" && asked.content.slice(0, 40) === job.text.slice(0, 40));
            if (saved && last?.role === "assistant") return { answer: last.content, tools_used: last.tools, conversation_id: convId };
          }
        } catch {}  // mạng chưa có lại: thử tiếp
        await new Promise((r) => setTimeout(r, 4000));
      }
      throw new Error(job.cancelled ? "Đã dừng" : "Mất kết nối quá lâu. Hãy mở lại đoạn chat từ danh sách bên trái để xem câu trả lời (nếu đã có).");
    };
    const streamChat = async (job, body) => {
      const ctrl = job.ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 180000);
      job.baseIds = new Set(state.convs.map((c) => c.id));
      job.base = job.convId != null ? api(`/api/conversations/${job.convId}`).then((c) => c.messages.length, () => null) : Promise.resolve(null);
      try {
        return await readStream(job, body, ctrl);
      } catch (err) {
        if (err.server || job.cancelled) throw err;
        return await recoverAnswer(job);  // gồm cả lúc luồng treo quá 180 giây
      } finally {
        clearTimeout(timer);
      }
    };
    // open(id): xem đoạn chat đã lưu; open(null, token): xem đoạn chat mới đang chờ trả lời; open(null): đoạn chat trống
    const open = async (id, token = null) => {
      state.chatId = id;
      state.chatJob = token;
      closeAsk?.();
      modelLocked = id != null || !!token;  // đoạn chat đã có (hoặc đang chờ trả lời) coi như đã chọn; đoạn chat trống thì hỏi lại từ đầu
      if (id == null && !token) resetModel();
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
      showModel(conv.model);
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

    // Câu cần suy luận mà đang dùng model mặc định: hỏi người dùng có nâng model không (hộp hỏi nằm trong khung chat, không chặn màn hình).
    // Trả về id model đã chọn, null nếu huỷ, undefined nếu không cần hỏi (câu tra cứu thường hoặc không kiểm tra được).
    const askUpgrade = async (text) => {
      let offer;
      try { offer = (await api("/api/chat/precheck", { method: "POST", body: { content: text } })).offer; } catch { return undefined; }
      if (!offer) return undefined;
      if (!log.querySelector(".cg-thread")) log.innerHTML = `<div class="cg-thread"></div>`;
      const thread = log.querySelector(".cg-thread");
      return new Promise((resolve) => {
        const card = document.createElement("div");
        card.className = "msg assistant ask-model";
        card.innerHTML = `<div class="av">AZB</div><div class="body"><div>${esc(offer.message)}</div>
          <div class="msg-actions">${offer.options.map((o) => `<button type="button" class="primary" data-model="${esc(o.id)}">${esc(o.label)}</button>`).join(" ")}
            <button type="button" data-model="${esc(ai.default_model)}">Giữ Haiku</button></div>
          <small class="muted">${offer.options.map((o) => esc(o.label.replace("Dùng ", "") + ": " + o.hint)).join(" · ")} · Esc để huỷ</small></div>`;
        const done = (v) => {
          closeAsk = null;
          card.remove();
          if (v === null && !thread.children.length) welcome();  // huỷ khi đoạn chat còn trống: trả lại màn hình chào
          resolve(v);
        };
        closeAsk = () => done(null);
        card.onclick = (e) => { const b = e.target.closest("button[data-model]"); if (b) done(b.dataset.model); };
        thread.appendChild(card);
        scroll();
      });
    };

    const send = async (text, model = chatModel) => {
      text = text.trim();
      if (closeAsk) return;  // đang chờ người dùng trả lời hộp hỏi nâng model
      if (attached.some((a) => a.status === "uploading" || a.status === "processing")) return toast("Đợi trợ lý đọc xong file đính kèm rồi hãy gửi.");
      if (text && !modelLocked && model === ai.default_model && !currentJob()) {
        const picked = await askUpgrade(text);
        if (picked === null) return;  // huỷ: câu hỏi vẫn nằm trong ô nhập
        if (picked !== undefined) {
          modelLocked = true;  // đã chọn trong đoạn chat này: không hỏi lại
          model = picked;
          showModel(picked);  // các câu sau trong đoạn chat này dùng model vừa chọn
        }
      }
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
        res = await streamChat(job, { content: text, conversation_id: job.convId, model });
      } catch (err) {
        if (job.cancelled) res = { answer: "Đã dừng trả lời theo yêu cầu (nhấn Esc). Câu hỏi được trả lại ô nhập để bạn sửa hoặc gửi lại.", error: "client" };
        else {
          const reason = err.name === "AbortError" ? "AI trả lời quá lâu, hãy thử lại sau ít phút." : err.message || "Không nhận được phản hồi từ máy chủ, hãy thử lại.";
          res = { answer: "Lỗi: " + reason, error: "client" };
        }
      }
      finishJob(job, res);
    };
    state.chatUI = { refreshList, setBusy, open, scroll, q };

    const autosize = () => {
      q.style.height = "auto";
      q.style.height = Math.min(q.scrollHeight, 220) + "px";
    };
    q.oninput = () => { closeAsk?.(); autosize(); };  // gõ tiếp thì bỏ hộp hỏi nâng model
    // Esc: huỷ hộp hỏi nâng model, hoặc dừng câu trả lời đang chờ của đoạn chat đang xem
    if (window.__chatEsc) document.removeEventListener("keydown", window.__chatEsc);
    window.__chatEsc = (e) => {
      if (e.key !== "Escape" || !$("#cg")) return;
      if (closeAsk) { closeAsk(); return; }
      const job = currentJob();
      if (job?.ctrl && !job.cancelled) { job.cancelled = true; job.ctrl.abort(); }
    };
    document.addEventListener("keydown", window.__chatEsc);
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
    // màn hình hẹp: khung lịch sử là lớp phủ, chọn xong thì đóng lại để thấy nội dung chat
    const closeSideIfNarrow = () => { if (matchMedia("(max-width: 960px)").matches) toggleSide(false); };
    $("#new-chat").onclick = $("#new-chat-2").onclick = () => { open(null); closeSideIfNarrow(); };
    // Lưu câu trả lời của AI thành đề xuất: tiêu đề lấy từ dòng đầu, nội dung là toàn bộ câu trả lời
    log.addEventListener("click", async (e) => {
      const btn = e.target.closest(".save-prop");
      if (!btn) return;
      const clone = btn.closest(".body").cloneNode(true);
      clone.querySelectorAll(".save-prop, .msg-actions, .tools").forEach((n) => n.remove());
      const text = clone.innerText.trim();
      const title = (text.split("\n").find((l) => l.trim()) || "Đề xuất").replace(/^[#*\->\s]+/, "").slice(0, 120);
      btn.disabled = true;
      try {
        await api("/api/proposals", { method: "POST", body: { title, body: text } });
        btn.textContent = "Đã lưu ✓";
      } catch (err) {
        btn.disabled = false;
        toast(err.message || "Không lưu được đề xuất, thử lại sau.");
      }
    });
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
      closeSideIfNarrow();
    };
    if (state.chatSeed) {  // câu hỏi soạn sẵn từ trang khác (VD: Mục tiêu doanh thu → Hỏi Trợ lý AI): mở đoạn chat mới và gửi luôn
      const seed = state.chatSeed;
      state.chatSeed = null;
      await open(null);
      send(seed);
      return;
    }
    await open(state.chatId);
  },
};

// Thanh hạn mức AI hôm nay trong ô chat: chỉ hiện phần trăm đã dùng và thời gian còn lại đến lúc reset, không hiện số tiền
function drawAiMeter() {
  const el = $("#cg-meter"), q = state.quota;
  if (!el) return;
  if (!q) { el.className = "cg-meter"; el.innerHTML = ""; return; }
  const h = Math.max(1, Math.round(q.resets_in_seconds / 3600));
  el.className = "cg-meter" + (q.percent >= 100 ? " full" : q.percent >= 80 ? " warn" : "");
  el.innerHTML = `<span>Hạn mức AI hôm nay</span><div class="quota-bar ${q.percent >= 100 ? "full" : q.percent >= 80 ? "warn" : ""}"><i style="width:${q.percent}%"></i></div>
    <span>${q.percent}% đã dùng · đặt lại sau ${h} giờ</span>`;
  el.title = q.scope === "company" ? "Ngân sách chung của công ty" : "Ngân sách cá nhân của bạn";
}

// Câu trả lời về tới dù người dùng đang xem đoạn chat khác hay trang khác: chỉ cập nhật màn hình nếu đúng đoạn đang xem
async function finishJob(job, res) {
  const viewing = state.chatJob === job.token || (job.convId != null && state.chatId === job.convId && !state.chatJob);
  state.jobs.delete(job.token);
  if (res.quota !== undefined) { state.quota = res.quota; drawAiMeter(); }
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
      pending.outerHTML = msgHtml({ role: "assistant", content: res.answer, tools: res.tools_used, error: !!res.error, usage: res.usage });
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
  list_targets: "mục tiêu trọng yếu",
  tao_file: "tạo file",
};

// Sơ đồ các bước từ nội dung quy trình (mỗi bước một dòng; bỏ số/gạch đầu dòng). Bước có "Nếu" hoặc "?" là điểm quyết định.
function processFlow(text) {
  const steps = String(text || "").split("\n")
    .map((l) => l.trim().replace(/^(?:[-*•]|\d+[.)]|bước\s*\d+\s*[:.)-]?)\s*/i, "").trim())
    .filter(Boolean)
    .slice(0, 30);
  if (steps.length < 2) return "";
  return `<ol class="flow">${steps.map((s, i) => `<li class="${/^nếu\b/i.test(s) || s.includes("?") ? "flow-decision" : ""}"><span class="flow-n">${i + 1}</span>${esc(s)}</li>`).join("")}</ol>`;
}

const modelName = (label) => String(label).replace(/^Claude\s+/i, "");  // "Claude Opus 5.5" → "Opus 5.5"

function msgHtml(m) {
  if (m.role === "user") return `<div class="msg user">${esc(m.content)}</div>`;
  const body = window.marked ? marked.parse(esc(m.content).replace(/&gt;/g, ">")) : esc(m.content);
  const labels = [...new Set((m.tools || []).map((t) => TOOL_LABELS[t] || "dữ liệu công ty"))];
  const tools = labels.length ? `<div class="tools">Đã tra cứu: ${labels.map(esc).join(", ")}</div>` : "";
  const save = m.error ? "" : `<div class="msg-actions"><button class="link save-prop">Lưu thành đề xuất</button></div>`;
  const u = m.usage;  // chỉ quản trị/TGĐ nhận được (server không gửi cho người khác); lượt đã lưu từ trước không có
  const used = u ? `<div class="msg-usage" title="Ước tính theo bảng giá, không phải hóa đơn">${fmtNum((u.input || 0) + (u.cache_read || 0) + (u.cache_write || 0))} token vào · ${fmtNum(u.output || 0)} token ra · ~$${Number(u.cost_usd || 0).toFixed(4)}</div>` : "";
  return `<div class="msg assistant ${m.error ? "error" : ""}"><div class="av">AZB</div><div class="body">${body}${tools}${used}${save}</div></div>`;
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
              <td>${p.employee_name ? esc(p.employee_name) + (p.employee_verified ? "" : ' <span class="badge warn">?</span>') : '<span class="badge warn">TBA – đang trống</span>'}${p.reports_to_name ? `<div class="muted small">báo cáo ${esc(p.reports_to_name)}</div>` : ""}</td>
              <td class="num">${p.headcount}</td>
              <td class="muted">${esc(p.notes || "")}</td>
              <td><button class="link" data-edit="${p.id}">Sửa</button> · <button class="link danger" data-del="${p.id}">Xoá</button></td>
            </tr>`).join("")}
        </table>` : '<div class="empty">Chưa có chức danh nào.</div>'}
      ${(() => {
        const members = sortByRank(emps.filter((e) => e.unit_id === u.id && e.status !== "inactive"));
        // Người phụ trách lấy theo chức danh đã đánh dấu ở bảng trên; chỉ khi đơn vị chưa đánh dấu ai mới suy theo ngạch
        const headIds = new Set(u.positions.filter((p) => p.is_head && p.employee_id).map((p) => p.employee_id));
        const isHeadRow = (e, i) => (headIds.size ? headIds.has(e.id) : i === 0 && isManager(e));
        return members.length ? `
          <h3 style="margin-top:20px">Nhân sự theo danh sách HCNS (${members.length})</h3>
          <table>
            <tr><th style="width:90px">Mã NV</th><th>Họ tên</th><th>Chức danh</th><th>Ngạch</th></tr>
            ${members.map((e, i) => `<tr><td><span class="badge">${esc(e.employee_code || "")}</span></td>
              <td><b>${esc(e.full_name)}</b> ${isHeadRow(e, i) ? '<span class="badge ok">Phụ trách</span>' : ""}</td>
              <td>${esc(e.job_title || "")}</td><td class="muted">${esc(e.grade || "")}</td></tr>`).join("")}
          </table>` : "";
      })()}
      <h3 style="margin-top:20px">Đơn vị trực thuộc</h3>
      ${u.children.length ? u.children.map((c) => `<button class="ghost child-btn" style="margin:0 6px 6px 0" data-child="${c.id}">${esc(c.name)}</button>`).join("")
        : '<div class="muted">Không có.</div>'}
      <div id="child-detail"></div>`;
    // Bấm đơn vị trực thuộc: xổ thông tin ngay bên dưới, không chuyển tab; bấm lại để thu gọn
    const childBox = $("#child-detail");
    body.querySelectorAll("[data-child]").forEach((b) => (b.onclick = async () => {
      const id = Number(b.dataset.child);
      if (b.classList.contains("active")) { b.classList.remove("active"); childBox.innerHTML = ""; return; }
      body.querySelectorAll("[data-child]").forEach((x) => x.classList.toggle("active", x === b));
      const c = await api(`/api/units/${id}`);
      const members = sortByRank(emps.filter((e) => e.unit_id === id && e.status !== "inactive"));
      childBox.innerHTML = `
        <div class="card" style="margin-top:10px">
          <div class="toolbar"><b>${esc(c.name)}</b><button class="link" onclick="go('units',{unitId:${id}})">Mở trang đơn vị</button></div>
          ${c.positions.length ? `<table>
            <tr><th>Chức danh</th><th>Người giữ</th><th>Định biên</th></tr>
            ${c.positions.map((p) => `<tr><td>${esc(p.title)} ${p.is_head ? '<span class="badge ok">Phụ trách</span>' : ""}</td>
              <td>${p.employee_name ? esc(p.employee_name) : '<span class="badge warn">TBA – đang trống</span>'}${p.reports_to_name ? `<div class="muted small">báo cáo ${esc(p.reports_to_name)}</div>` : ""}</td><td class="num">${p.headcount}</td></tr>`).join("")}
          </table>` : '<div class="muted">Chưa có chức danh.</div>'}
          ${members.length ? `<h4 style="margin:12px 0 6px">Nhân sự (${members.length})</h4><table>
            <tr><th style="width:90px">Mã NV</th><th>Họ tên</th><th>Chức danh</th></tr>
            ${members.map((e) => `<tr><td><span class="badge">${esc(e.employee_code || "")}</span></td><td><b>${esc(e.full_name)}</b></td><td>${esc(e.job_title || "")}</td></tr>`).join("")}
          </table>` : ""}
        </div>`;
    }));
    const form = (p) => openForm(p.id ? "Sửa chức danh" : "Thêm chức danh", [
      { name: "title", label: "Chức danh", required: true, placeholder: "VD: Trưởng phòng" },
      { name: "title_code", label: "Mã chức danh", placeholder: "TP, PP, GĐ, NV..." },
      { name: "employee_id", label: "Người giữ", type: "select", search: true, placeholder: "Gõ tên nhân sự để tìm (để trống = đang trống)...", numeric: true, options: [["", "— Đang trống (TBA) —"], ...emps.map((e) => [e.id, e.full_name])] },
      { name: "is_head", label: "Là người phụ trách đơn vị?", type: "select", numeric: true, options: [[0, "Không"], [1, "Có"]] },
      { name: "reports_to_employee_id", label: "Báo cáo cho", type: "select", search: true, placeholder: "Gõ tên để tìm (để trống = theo cây tổ chức)...", numeric: true, options: [["", "— Theo cây tổ chức —"], ...emps.map((e) => [e.id, e.full_name])] },
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
          ${p.content ? `<details><summary>Nội dung các bước</summary><div class="process-content">${esc(p.content)}</div></details>
            <details><summary>Sơ đồ các bước</summary>${processFlow(p.content) || '<div class="muted">Chưa đủ để vẽ sơ đồ: cần ít nhất 2 bước, mỗi bước một dòng.</div>'}</details>` : ""}
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
      <div class="toolbar"><h3 style="margin:0">Mục tiêu trọng yếu</h3><button class="primary" id="add-tg">+ Thêm mục tiêu</button></div>
      ${u.targets.length ? `
        <table>
          <tr><th>Kỳ</th><th>Chỉ tiêu</th><th class="num">Mục tiêu</th><th class="num">Thực hiện</th><th class="num">% đạt</th><th>Ghi chú</th><th></th></tr>
          ${u.targets.map((t) => `
            <tr>
              <td>${esc(t.period)}</td>
              <td>${esc(t.metric === "khac" && t.metric_name ? t.metric_name : METRICS[t.metric] || t.metric)}</td>
              <td class="num">${fmtNum(t.target_value)} <span class="muted">${esc(t.unit_label || "")}</span></td>
              <td class="num">${fmtNum(t.actual_value)}</td>
              <td class="num">${t.target_value && t.actual_value != null ? Math.round((t.actual_value / t.target_value) * 100) + "%" : "—"}</td>
              <td class="muted">${esc(t.notes || "")}</td>
              <td><button class="link" data-edit="${t.id}">Sửa</button> · <button class="link danger" data-del="${t.id}">Xoá</button></td>
            </tr>`).join("")}
        </table>` : '<div class="empty">Chưa có mục tiêu. Bấm “Thêm mục tiêu” để nhập khi có số liệu.</div>'}`;
    const form = (t) => !t.id ? openForm("Thêm mục tiêu", [
      ...periodFields(),
      ...keyMetricFields(),
    ], periodValues(), (raw) => saveKeyMetrics(raw, u.id, joinPeriod(raw))) : openForm("Sửa mục tiêu", [
      { name: "period", label: "Kỳ", required: true, placeholder: "2026, 2026-Q4 hoặc 2026-10" },
      { name: "metric", label: "Loại chỉ tiêu", type: "select", options: Object.entries(METRICS), default: "doanh_thu" },
      { name: "metric_name", label: "Tên chỉ tiêu (nếu là chỉ tiêu khác)" },
      { name: "target_value", label: "Giá trị mục tiêu", type: "number" },
      { name: "actual_value", label: "Giá trị thực hiện", type: "number" },
      { name: "unit_label", label: "Đơn vị tính", default: "VNĐ" },
      { name: "notes", label: "Ghi chú", type: "textarea" },
    ], t, (raw) => {
      // Tên chỉ tiêu chỉ dùng cho "Chỉ tiêu khác"; các loại còn lại dùng tên chuẩn, tránh lưu chữ nhập bừa như "ok".
      const data = { ...raw, metric_name: raw.metric === "khac" ? String(raw.metric_name || "").trim() : "" };
      if (raw.metric === "khac" && !data.metric_name) throw new Error("loại “Chỉ tiêu khác” cần có tên chỉ tiêu.");
      return t.id ? api(`/api/targets/${t.id}`, { method: "PUT", body: data }) : api("/api/targets", { method: "POST", body: { ...data, unit_id: u.id } });
    });
    $("#add-tg").onclick = () => form({});
    body.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => form(u.targets.find((t) => t.id == b.dataset.edit))));
    body.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => confirmDelete("targets", b.dataset.del, "mục tiêu này")));
  },

  async docs(body, u) {
    const [meta, units] = await Promise.all([api("/api/documents/meta"), api("/api/units")]);
    const own = u.documents.filter((d) => d.is_owner), shared = u.documents.filter((d) => !d.is_owner);
    const section = (title, hint, list) => `<section class="doc-section">
      <div class="doc-section-head"><b>${title}</b><span class="badge">${list.length}</span><span class="muted">${hint}</span></div>
      ${docTable(list, false)}</section>`;
    body.innerHTML = `
      <div class="toolbar"><div><h3 style="margin:0">Tài liệu của đơn vị</h3>
        <div class="muted">${u.documents.length ? `${own.length} thuộc đơn vị · ${shared.length} dùng chung từ phòng ban khác` : "Chưa có tài liệu nào"}</div></div>
        ${can("docs_edit") ? `<div><button class="ghost" id="pick-doc">${icon("plus")}Thêm tài liệu có sẵn</button>${DOC_ACTIONS}</div>` : ""}</div>
      ${u.documents.length ? `
        ${own.length ? section("Của đơn vị", "đơn vị này là chủ quản", own) : ""}
        ${shared.length ? section("Dùng chung từ phòng ban khác", "chỉ gỡ khỏi đơn vị này, không xoá tài liệu gốc", shared) : ""}`
        : '<div class="empty">Chưa có tài liệu. Tải lên quy trình ISO, hướng dẫn, biểu mẫu của đơn vị, hoặc thêm tài liệu đã có trong thư viện.</div>'}`;
    if (can("docs_edit")) {
      $("#up-doc").onclick = () => uploadForm(meta, units, u.id);
      $("#url-doc").onclick = () => urlLearnForm(units, u.id);
      $("#pick-doc").onclick = () => linkExistingDocs(u);
      body.querySelectorAll("[data-unlink-doc]").forEach((b) => (b.onclick = async () => {
        const id = Number(b.dataset.unlinkDoc), d = await api(`/api/documents/${id}`);
        try {
          await api(`/api/documents/${id}`, { method: "PUT", body: { shared_unit_ids: d.shared_unit_ids.filter((x) => x !== u.id) } });
          render();
        } catch (e) { toast(e.message, "err"); }
      }));
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

// Khớp tên không dấu: mỗi từ gõ vào phải là phần đầu của một từ trong văn bản (không cần đúng thứ tự)
const foldVN = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").toLowerCase();
const wordsVN = (s) => foldVN(s).split(/[^a-z0-9]+/).filter(Boolean);  // tách từ, bỏ dấu và dấu câu
function matchWords(query, text) {
  const q = wordsVN(query), hay = wordsVN(text);
  return q.every((t) => hay.some((w) => w.startsWith(t)));
}

// Thay hộp chọn mặc định của trình duyệt (thanh cuộn, viền cứng) bằng menu tự vẽ; <select> gốc vẫn giữ giá trị và sự kiện change.
// Sau khi gán sel.value bằng code, gọi sel.dispatchEvent(new Event("sync")) để nhãn cập nhật theo.
// searchable: thêm ô gõ để lọc các mục (dùng khi danh sách dài).
function enhanceSelect(sel, { searchable = false } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "dd";
  sel.before(wrap);
  wrap.append(sel);
  sel.classList.add("dd-native");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "dd-btn";
  const menu = document.createElement("div");
  menu.className = "dd-menu";
  menu.setAttribute("role", "listbox");
  const search = document.createElement("input");
  search.className = "dd-search";
  search.placeholder = "Tìm…";
  search.autocomplete = "off";
  const list = document.createElement("div");
  list.className = "dd-list";
  if (searchable) menu.append(search);
  menu.append(list);
  wrap.append(btn, menu);
  const close = () => { wrap.classList.remove("open"); document.removeEventListener("click", onDoc, true); };
  const onDoc = (e) => { if (!wrap.contains(e.target)) close(); };
  const paintList = () => {
    const opts = [...sel.options].filter((o) => !search.value.trim() || matchWords(search.value, o.textContent));
    list.innerHTML = opts.length ? opts.map((o) =>
      `<button type="button" role="option" class="dd-opt${o.value === sel.value ? " sel" : ""}" data-v="${esc(o.value)}">${esc(o.textContent)}</button>`).join("")
      : '<div class="dd-empty">Không có mục nào khớp</div>';
  };
  const sync = () => {
    const cur = sel.selectedOptions[0];
    btn.textContent = cur ? cur.textContent : "";
    btn.classList.toggle("active", !!sel.value);
    paintList();
  };
  btn.onclick = () => {
    if (wrap.classList.contains("open")) return close();
    search.value = "";
    sync();
    wrap.classList.add("open");
    document.addEventListener("click", onDoc, true);
    if (searchable) search.focus({ preventScroll: true });
    menu.querySelector(".sel")?.scrollIntoView({ block: "nearest" });
  };
  search.oninput = paintList;
  search.onkeydown = (e) => {  // Enter chọn mục khớp đầu tiên
    if (e.key !== "Enter") return;
    e.preventDefault();
    list.querySelector(".dd-opt")?.click();
  };
  menu.onclick = (e) => {
    const o = e.target.closest(".dd-opt");
    if (!o) return;
    sel.value = o.dataset.v;
    sel.dispatchEvent(new Event("change"));
    sync();
    close();
  };
  wrap.onkeydown = (e) => { if (e.key === "Escape") { close(); btn.focus(); } };
  sel.addEventListener("sync", sync);
  sync();
}

const isAiPdf = (d) => !!d.ai_read;  // PDF do AI đọc (backend xác định theo cấu trúc, không theo chữ trong ghi chú)
function reviewLabel(d) {
  const done = d.reviewed_pages || 0, total = d.page_count || 0;
  if (total && done >= total) return "✓ Đã đối chiếu đủ";
  return done ? `Đối chiếu (${done}/${total} trang)` : "Đối chiếu bản gốc";
}
const isUnreviewed = (d) => needsReview(d);  // PDF scan do AI đọc, chưa đối chiếu đủ từng trang

// Khung chữ khi đối chiếu: sửa thẳng trên bản đã dựng (contenteditable); tab "Markdown" là ô mã gốc #rv-text, nguồn dữ liệu khi lưu.
// Chỉ đổi HTML ngược về markdown khi người duyệt thật sự gõ (dirty), để bản chưa sửa giữ nguyên từng ký tự.
const rvRender = (text) => window.marked ? marked.parse(esc(text).replace(/&gt;/g, ">"), { breaks: true }).replace(/<li><\/li>/g, "<li><br></li>") : `<pre>${esc(text)}</pre>`;
let rvTd;
function rvToMd(html) {
  if (!rvTd) {
    rvTd = new TurndownService({ headingStyle: "atx", bulletListMarker: "*", emDelimiter: "*", hr: "---" });
    if (window.turndownPluginGfm) rvTd.use(turndownPluginGfm.gfm);
  }
  return rvTd.turndown(html);
}
function rvTextHtml(text, editable) {
  return `${editable ? '<div class="rv-tabs"><button type="button" class="rv-code" title="Xem và sửa mã markdown gốc">‹/› Mã</button></div>' : ""}
    <div id="rv-view" class="rv-view" ${editable && window.TurndownService ? 'contenteditable="true" spellcheck="false"' : ""}>${rvRender(text)}</div>
    <textarea id="rv-text" class="rv-text" hidden ${editable ? "" : "readonly"}>${esc(text)}</textarea>`;
}
// Lấy chữ hiện tại của khung (đồng bộ từ bản soạn thảo nếu đã sửa ở đó)
function rvSync(root) {
  const view = root.querySelector("#rv-view"), area = root.querySelector("#rv-text");
  if (view.dataset.dirty) { area.value = rvToMd(view.innerHTML); delete view.dataset.dirty; }
  return area.value;
}
// Như Word: Enter trên dòng trống, hoặc Backspace ở đầu dòng, của một mục danh sách thì lùi ra một cấp.
// Một mục có thể chứa nhiều dòng (<br>) hoặc nhiều đoạn (<p>), nên xét theo dòng chứa con trỏ chứ không theo cả mục:
// cấp ngoài cùng thì dòng đó và các dòng/đoạn sau nó thành đoạn thường (các mục phía sau tách thành danh sách mới), cấp con thì đưa lên cấp mục cha.
function rvExitList(view, key) {
  const sel = getSelection();
  if (!sel.rangeCount || !sel.isCollapsed || !view.contains(sel.anchorNode)) return false;
  const node = sel.anchorNode, off = sel.anchorOffset;
  const li = (node.nodeType === 1 ? node : node.parentElement).closest("li");
  if (!li || !view.contains(li) || li.querySelector("ul, ol")) return false;
  const isBlock = (n) => !!n && n.nodeType === 1 && /^(P|DIV)$/.test(n.tagName);
  const isBlank = (n) => !!n && n.nodeType === 3 && !n.textContent.trim();
  const isBr = (n) => !!n && n.nodeName === "BR";
  const nextReal = (n) => { for (n = n && n.nextSibling; isBlank(n); n = n.nextSibling); return n; };
  // `at`: con trực tiếp của mục nằm ngay tại con trỏ (null = con trỏ ở cuối mục)
  let at;
  if (node === li) at = li.childNodes[off] || null;
  else {
    for (at = node; at.parentNode !== li; at = at.parentNode);
    const r = document.createRange();
    r.setStart(at, 0);
    r.setEnd(node, off);
    if (r.toString()) return false;  // con trỏ giữa chữ
  }
  let prev = at ? at.previousSibling : li.lastChild;
  while (isBlank(prev)) prev = prev.previousSibling;
  if (prev && !isBr(prev) && !isBlock(prev)) return false;  // không phải đầu dòng
  if (key === "Enter") {
    const emptyLine = !at || isBr(at) || (isBlock(at) && !at.textContent.trim() && !at.querySelector("img")) ||
      (isBlank(at) && (!nextReal(at) || isBr(nextReal(at)) || isBlock(nextReal(at))));
    if (!emptyLine) return false;
  }
  const list = li.parentElement, outer = list.parentElement.closest("li");
  const kept = [];
  for (let n = li.firstChild; n && n !== at; n = n.nextSibling) kept.push(n);
  const hasKept = kept.some((n) => !isBlank(n) && !isBr(n));
  const tail = [];
  for (let n = li.nextElementSibling; n; n = n.nextElementSibling) tail.push(n);
  if (outer && view.contains(outer)) {  // cấp con: đưa cả mục lên cấp của mục cha, các mục sau thành con của mục này
    if (hasKept) return false;
    if (tail.length) {
      const rest = document.createElement(list.tagName);
      tail.forEach((n) => rest.appendChild(n));
      li.appendChild(rest);
    }
    outer.after(li);
    if (!li.firstChild) li.innerHTML = "<br>";
    if (!list.children.length) list.remove();
    sel.collapse(li, 0);
    return true;
  }
  const lifted = [];
  for (let n = at; n; n = n.nextSibling) lifted.push(n);
  // dòng trống đứng đầu: bỏ <br> kết thúc dòng đó nếu phía sau còn nội dung (dòng trống biến mất cùng dấu bullet)
  if (isBr(lifted[0]) && lifted.slice(1).some((n) => !isBlank(n))) lifted.shift().remove();
  const out = [];
  let run = null;
  for (const n of lifted) {
    if (isBlock(n)) { run = null; out.push(n); }
    else { if (!run) { run = document.createElement("p"); out.push(run); } run.appendChild(n); }
  }
  if (!out.length) out.push(document.createElement("p"));
  out.forEach((p) => { if (!p.textContent.trim() && !p.querySelector("br, img")) p.innerHTML = "<br>"; });
  let anchor = list;
  out.forEach((n) => { anchor.after(n); anchor = n; });
  if (tail.length) {
    const rest = document.createElement(list.tagName);
    tail.forEach((n) => rest.appendChild(n));
    anchor.after(rest);
  }
  // phần còn lại của mục: bỏ <br> cuối (đã thành ranh giới đoạn); mục không còn gì thì xoá luôn
  while (isBlank(li.lastChild)) li.lastChild.remove();
  if (isBr(li.lastChild)) li.lastChild.remove();
  while (isBlank(li.lastChild)) li.lastChild.remove();
  if (!li.textContent.trim() && !li.querySelector("img")) li.remove();
  if (!list.children.length) list.remove();
  sel.collapse(out[0], 0);
  return true;
}
function rvWireTabs(root) {
  const view = root.querySelector("#rv-view"), area = root.querySelector("#rv-text");
  view.addEventListener("input", () => { view.dataset.dirty = "1"; });
  view.addEventListener("paste", (e) => { e.preventDefault(); document.execCommand("insertText", false, e.clipboardData.getData("text/plain")); });
  view.addEventListener("keydown", (e) => {
    if ((e.key !== "Enter" && e.key !== "Backspace") || e.shiftKey || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
    if (rvExitList(view, e.key)) { e.preventDefault(); e.stopImmediatePropagation(); view.dataset.dirty = "1"; }
  });
  // Enter ở cuối dòng của mục cha (có danh sách con): thêm mục con đầu tiên ngay trong khối, thay vì để trình duyệt nhảy xuống mục cha kế tiếp
  view.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    const sel = getSelection();
    if (!sel.rangeCount || !sel.isCollapsed) return;
    const li = (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement).closest("li");
    const sub = li && [...li.children].find((c) => c.tagName === "UL" || c.tagName === "OL");
    if (!sub || !view.contains(li)) return;
    const rest = document.createRange();
    rest.setStart(sel.anchorNode, sel.anchorOffset);
    rest.setEndBefore(sub);
    if (rest.toString().trim()) return;  // còn chữ phía sau con trỏ: giữ hành vi mặc định
    e.preventDefault();
    const item = document.createElement("li");
    item.innerHTML = "<br>";
    sub.insertBefore(item, sub.firstChild);
    sel.collapse(item, 0);
    view.dataset.dirty = "1";
  });
  const code = root.querySelector(".rv-code");
  if (code) code.onclick = () => {
    const edit = area.hidden;  // đang ở khung soạn thảo thì chuyển sang mã
    if (edit) rvSync(root); else view.innerHTML = rvRender(area.value);
    view.hidden = edit; area.hidden = !edit;
    code.textContent = edit ? "← Soạn thảo" : "‹/› Mã";
    (edit ? area : view).focus();
  };
}

// Trả về hàm báo còn chữ sửa chưa lưu (nhãn nút xác nhận giữ nguyên)
function rvTrack(root, original) {
  return () => rvSync(root).trim() !== (original || "").trim();
}
const rvLeave = (changed) => !changed() || confirm("Trang này có chữ đã sửa nhưng chưa lưu. Bỏ thay đổi?");

// Đối chiếu từng trang: ảnh trang gốc bên trái, chữ AI đã đọc bên phải; người duyệt xác nhận đúng hoặc sửa tại chỗ
async function reviewDoc(docId, onClose) {
  const modal = $("#modal"), body = $("#modal-body");
  let data;
  try { data = await api(`/api/documents/${docId}/review`); } catch (e) { toast(e.message, "err"); return; }
  const editable = can("docs_edit");
  if (data.whole) return reviewWhole(docId, data, onClose);
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
        <div class="rv-img"><a href="/api/documents/${docId}/page/${cur}.png" target="_blank" rel="noopener" title="Bấm để mở ảnh cỡ lớn"><img src="/api/documents/${docId}/page/${cur}.png" alt="Trang ${cur} bản gốc"></a></div>
        <div>${rvTextHtml(p.text, editable)}
          <div class="rv-bar">
            <button type="button" class="ghost" id="rv-prev" ${cur <= 1 ? "disabled" : ""}>◀ Trước</button>
            <span class="muted">Trang ${cur}/${data.total}</span>
            <button type="button" class="ghost" id="rv-next" ${cur >= data.total ? "disabled" : ""}>Sau ▶</button>
            ${editable ? `<button type="button" class="primary" id="rv-ok">${"✓ Chữ khớp bản gốc – sang trang sau"}</button>
            ${p.status ? `<button type="button" class="ghost" id="rv-undo" title="${p.status === "edited" ? "Bỏ dấu đã đối chiếu (chữ đã sửa vẫn giữ nguyên)" : "Bỏ dấu đã đối chiếu"}">↩ Bỏ xác nhận trang này</button>` : ""}` : ""}
          </div></div></div>`;
    rvWireTabs(body);
    const changed = rvTrack(body, p.text);
    body.querySelectorAll(".rv-chips [data-pg]").forEach((b) => (b.onclick = () => { if (rvLeave(changed)) { cur = +b.dataset.pg; draw(); } }));
    $("#rv-prev").onclick = () => { if (rvLeave(changed)) { cur--; draw(); } };
    $("#rv-next").onclick = () => { if (rvLeave(changed)) { cur++; draw(); } };
    const undo = $("#rv-undo");
    if (undo) undo.onclick = async () => {
      undo.disabled = true;
      try { await api(`/api/documents/${docId}/review/${cur}`, { method: "DELETE" }); p.status = null; draw(); }
      catch (e) { toast(e.message, "err"); undo.disabled = false; }
    };
    const ok = $("#rv-ok");
    if (ok) ok.onclick = async () => {
      const text = rvSync(body);
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

// Đối chiếu cả file: văn bản AI đọc không có đánh dấu trang nên không ghép từng trang được. Các trang gốc xếp dọc bên trái, toàn bộ chữ bên phải.
function reviewWhole(docId, data, onClose) {
  const modal = $("#modal"), body = $("#modal-body");
  const editable = can("docs_edit");
  let status = data.status;
  $("#modal-title").textContent = `Đối chiếu: ${data.title}`;
  modal.classList.add("wide");
  $("#modal-ok").textContent = "Đóng";
  $("#modal-cancel").style.display = "none";
  $("#modal-form").onsubmit = (e) => { e.preventDefault(); modal.close(); };
  modal.addEventListener("close", () => { modal.classList.remove("wide"); $("#modal-cancel").style.display = ""; onClose && onClose(); }, { once: true });
  const draw = () => {
    body.innerHTML = `<div class="muted" style="margin-bottom:8px">${status ? (status === "edited" ? "✓ Đã đối chiếu và sửa" : "✓ Đã đối chiếu") : `Chưa đối chiếu · ${data.total} trang`} – văn bản này không chia theo trang, nên đối chiếu cả file một lần.</div>
      <div class="rv-grid">
        <div class="rv-img" style="max-height:70vh;overflow:auto">${Array.from({ length: data.total }, (_, i) =>
          `<img loading="lazy" src="/api/documents/${docId}/page/${i + 1}.png" alt="Trang ${i + 1} bản gốc" style="margin-bottom:8px">`).join("")}</div>
        <div>${rvTextHtml(data.text, editable)}
          <div class="rv-bar">
            ${editable ? `<button type="button" class="primary" id="rv-ok">✓ Chữ khớp bản gốc</button>
            ${status ? '<button type="button" class="ghost" id="rv-undo">↩ Bỏ xác nhận</button>' : ""}` : ""}
          </div></div></div>`;
    rvWireTabs(body);
    rvTrack(body, data.text);
    const undo = $("#rv-undo");
    if (undo) undo.onclick = async () => {
      undo.disabled = true;
      try { await api(`/api/documents/${docId}/review`, { method: "DELETE" }); status = null; draw(); }
      catch (e) { toast(e.message, "err"); undo.disabled = false; }
    };
    const ok = $("#rv-ok");
    if (ok) ok.onclick = async () => {
      const text = rvSync(body);
      ok.disabled = true;
      try {
        const r = await api(`/api/documents/${docId}/review`, { method: "PUT", body: text.trim() !== (data.text || "").trim() ? { text } : {} });
        status = r.status; data.text = text.trim(); draw();
      } catch (e) { toast(e.message, "err"); ok.disabled = false; }
    };
  };
  draw();
  modal.showModal();
}

// Người tải lên: bấm mở đúng hồ sơ nhân sự theo id (không theo tên, vì có thể trùng tên); kèm đơn vị để phân biệt
function uploaderHtml(d) {
  const unit = d.uploader_unit ? ` · ${esc(d.uploader_unit)}` : "";
  if (!d.uploader_employee_id || !canSee("people")) return `${esc(d.uploader_name)}${unit}`;
  return `<button class="link" onclick="document.querySelector('#modal').close();go('people',{peopleQuery:'',peopleFocus:${Number(d.uploader_employee_id)},peopleReveal:true})">${esc(d.uploader_name)}</button>${unit}`;
}

const isAiNote = (d) => d.extract_status === "ok" && /AI/.test(d.extract_note || "");
// PDF do AI đọc: đã đối chiếu đủ các trang / còn cần đối chiếu (kể cả file máy chủ báo chưa mở được màn đối chiếu)
const reviewDone = (d) => isAiPdf(d) && !!d.page_count && (d.reviewed_pages || 0) >= d.page_count;
const cannotReview = (d) => isAiPdf(d) && !reviewDone(d) && d.can_review === false;  // mất file PDF gốc trên máy chủ
const needsReview = (d) => isAiPdf(d) && !reviewDone(d) && d.can_review !== false;
// Dòng cảnh báo màu vàng dưới tên file (ghi chú đọc/đối chiếu); lỗi chưa đọc được hiện màu đỏ nên không tính
const hasWarnNote = (d) => !!d.extract_note && !isAiNote(d) && !DOC_UNREAD.has(d.extract_status);

function docTable(docs, showUnit, query = "") {
  if (!docs.length) return '<div class="empty">Chưa có tài liệu nào.</div>';
  // Danh sách 3 cột: thông tin (tên + một dòng phụ) | trạng thái (chỉ nổi bật khi cần chú ý) | thao tác (icon)
  const fmtDay = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || ""); return m ? `${m[3]}/${m[2]}/${m[1]}` : ""; };
  // Chỉ hiện khi có gì cần chú ý: lỗi/đang xử lý, hoặc PDF AI đọc mà đối chiếu được. File bình thường để trống.
  const stateCell = (d) => {
    const [lbl, cls] = DOC_STATUS[d.extract_status] || [d.extract_status, ""];
    if (d.extract_status !== "ok") return `<span class="badge ${cls}">${lbl}</span>`;
    if (!isAiPdf(d)) return "";
    if (reviewDone(d)) return `<button class="link doc-reviewed" data-review-doc="${d.id}" title="Mở lại để xem">${reviewLabel(d)}</button>`;
    // can_review === false: máy chủ không còn file PDF gốc để đặt cạnh văn bản → cần tải lại file
    if (d.can_review === false) return `<span class="badge" title="Máy chủ không còn file PDF gốc nên không đối chiếu được. Tải lại file này lên rồi đối chiếu.">Không mở được đối chiếu</span>`;
    return `<button class="badge doc-review warn" data-review-doc="${d.id}" title="${esc(d.extract_note)}">${reviewLabel(d)}</button>`;
  };
  return `<table class="doc-list">
    ${docs.map((d) => {
      const unread = DOC_UNREAD.has(d.extract_status);
      const meta = [
        showUnit ? (d.unit_id ? `<button class="link" onclick="go('units',{unitId:${d.unit_id}, unitTab:'docs'})">${esc(d.unit_name)}</button>` : "Chung") : "",
        showUnit && (d.shared_units || []).length ? `cũng ở ${d.shared_units.map((x) => `<button class="link" onclick="go('units',{unitId:${x.id}, unitTab:'docs'})">${esc(x.name)}</button>`).join(", ")}` : "",
        d.is_owner === false ? `<span class="badge">Từ ${esc(d.owner_unit_name || "Tài liệu chung")}</span>` : "",
        d.is_owner && d.other_units ? `<span title="Cũng hiển thị ở các phòng ban này">Cũng ở ${esc(d.other_units)}</span>` : "",
        esc(DOC_LABELS[d.doc_type] || d.doc_type),
        d.page_count ? `${d.page_count} trang` : "",
        fmtSize(d.size_bytes),
        fmtDay(d.uploaded_at) ? `${fmtDay(d.uploaded_at)}${d.uploader_name ? ` · ${uploaderHtml(d)}` : ""}` : "",
        isAiNote(d) && !isAiPdf(d) ?`<span title="${esc(d.extract_note)}">Đọc bằng AI</span>` : "",
      ].filter(Boolean).join(" · ");
      const label = query ? hlDoc(`${d.code || ""} ${d.title}`.trim(), query) : `${esc(d.code || "")} ${esc(d.title)}`;
      return `<tr${unread ? ' class="row-bad"' : ""}>
        <td class="doc-main">${docHref(d) ? `<a class="doc-title" href="${esc(docHref(d))}" target="_blank" rel="noopener" title="${esc(d.filename)}">` : ""}${label}${docHref(d) ? "</a>" : ""}${d.version ? ` <span class="badge">v${esc(d.version)}</span>` : ""}${d.access_level && d.access_level !== "internal" ? ` <span class="badge ${d.access_level === "secret" || d.access_level === "restricted" ? "warn" : ""}">${esc(ACCESS_LABELS[d.access_level] || d.access_level)}</span>` : ""}
          <div class="doc-meta">${meta}</div>
          ${query && d.snippet ? `<div class="doc-snippet">${hlDoc(d.snippet, query)}</div>` : ""}
          ${d.extract_note && !isAiNote(d) ? `<div class="doc-note${unread ? " bad" : ""}">${esc(d.extract_note)}</div>` : ""}</td>
        <td class="doc-state">${stateCell(d)}</td>
        <td class="row-actions doc-acts">
          ${can("docs_download") ? `<a class="row-icon-btn" href="/api/documents/${d.id}/file" target="_blank" title="Tải về" aria-label="Tải về">${icon("download")}</a>` : ""}
          ${can("docs_edit") || can("docs_delete") ? `<details class="doc-more doc-edit"><summary class="row-icon-btn" title="Thêm" aria-label="Thêm thao tác">⋯</summary><div>${can("docs_edit") ? `<button class="link" data-edit-doc="${d.id}">${icon("edit")}Sửa thông tin</button><button class="link" data-reproc="${d.id}">${icon("reset")}Đọc lại</button>${d.is_owner === false ? `<button class="link" data-unlink-doc="${d.id}">${icon("trash")}Gỡ khỏi đơn vị này</button>` : ""}` : ""}${can("docs_delete") ? `<button class="link danger" data-del-doc="${d.id}">${icon("trash")}Xoá</button>` : ""}</div></details>` : ""}</td>
      </tr>`;
    }).join("")}
  </table>`;
}

// Đóng menu "⋯" của danh sách tài liệu khi bấm ra ngoài
document.addEventListener("click", (e) => {
  document.querySelectorAll("details.doc-more[open]").forEach((m) => { if (!m.contains(e.target)) m.open = false; });
});

// Thêm tài liệu đã có trong thư viện vào đơn vị này (tài liệu hiện ở nhiều phòng ban, chỉ lưu một bản)
async function linkExistingDocs(u) {
  const all = (await api("/api/documents")).filter((d) => d.unit_id !== u.id && !(d.shared_units || []).some((x) => x.id === u.id));
  const modal = $("#modal"), body = $("#modal-body"), ok = $("#modal-ok"), form = $("#modal-form");
  const plain = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").toLowerCase();
  const picked = new Set();
  $("#modal-title").textContent = `Thêm tài liệu vào ${u.name}`;
  body.innerHTML = `<input type="search" id="lk-q" placeholder="Tìm theo tên hoặc mã tài liệu..." autocomplete="off">
    <div id="lk-list" class="link-docs"></div><p class="muted" id="lk-sum"></p>`;
  const draw = () => {
    const q = plain($("#lk-q").value.trim());
    const hits = all.filter((d) => !q || plain(`${d.code || ""} ${d.title}`).includes(q)).slice(0, 80);
    $("#lk-list").innerHTML = hits.length ? hits.map((d) => `<label class="link-doc"><input type="checkbox" value="${d.id}" ${picked.has(d.id) ? "checked" : ""}>
      <span><b>${esc((d.code ? d.code + " – " : "") + d.title)}</b><small>${esc(d.unit_name || "Tài liệu chung")} · ${esc(DOC_LABELS[d.doc_type] || d.doc_type)}</small></span></label>`).join("")
      : '<div class="empty">Không có tài liệu nào để thêm.</div>';
    $("#lk-sum").textContent = picked.size ? `Đã chọn ${picked.size} tài liệu` : "";
    ok.disabled = !picked.size;
  };
  $("#lk-q").oninput = draw;
  $("#lk-list").onchange = (e) => { const id = Number(e.target.value); e.target.checked ? picked.add(id) : picked.delete(id); draw(); };
  ok.textContent = "Thêm vào đơn vị";
  $("#modal-cancel").onclick = () => modal.close();
  form.onsubmit = async (e) => {
    e.preventDefault();
    ok.disabled = true;
    try {
      for (const id of picked) {
        const d = await api(`/api/documents/${id}`);
        await api(`/api/documents/${id}`, { method: "PUT", body: { shared_unit_ids: [...(d.shared_unit_ids || []), u.id] } });
      }
      modal.close();
      render();
    } catch (err) { toast("Không thêm được: " + err.message, "err"); ok.disabled = false; }
  };
  modal.addEventListener("close", () => { ok.textContent = "Lưu"; ok.disabled = false; }, { once: true });
  draw();
  modal.showModal();
}

function uploadForm(meta, units, unitId) {
  openForm("Tải tài liệu lên", [
    { name: "file", label: "File", type: "file", required: true, accept: meta.allowed_ext.join(",") },
    { name: "title", label: "Tên tài liệu (để trống = lấy theo tên file)" },
    { name: "code", label: "Mã tài liệu", placeholder: "VD: QT-HCNS-01" },
    { name: "version", label: "Phiên bản / lần ban hành" },
    { name: "doc_type", label: "Loại", type: "select", options: Object.entries(meta.types), default: "quy_trinh" },
    { name: "unit_ids", label: "Phòng ban (chọn nhiều; ★ = đơn vị chủ quản)", type: "units", ordered: true, empty: "Tài liệu chung công ty (chưa chọn phòng ban)", placeholder: "Gõ tên phòng ban để thêm...", options: units.map((u) => [u.id, u.name]) },
    { name: "access_level", label: "Độ mật (ai được xem, kể cả qua trợ lý AI)", type: "select", options: meta.levels, default: meta.default_level },
  ], { unit_ids: unitId ? [unitId] : [] }, ({ unit_ids, ...d }) => {
    const fd = new FormData();
    Object.entries({ ...d, unit_id: unit_ids[0] ?? "", shared_unit_ids: unit_ids.slice(1).join(",") }).forEach(([k, v]) => v !== "" && v != null && fd.append(k, v));
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
      { name: "unit_ids", label: "Phòng ban (chọn nhiều; ★ = đơn vị chủ quản)", type: "units", ordered: true, empty: "Tài liệu chung công ty (chưa chọn phòng ban)", placeholder: "Gõ tên phòng ban để thêm...", options: units.map((u) => [u.id, u.name]) },
      { name: "access_level", label: "Độ mật (ai được xem, kể cả qua trợ lý AI)", type: "select", options: d.access_level === "secret" && !meta.levels.some(([k]) => k === "secret") ? [["secret", "Mật (chỉ Ban TGĐ/Admin)"]] : meta.levels },
    ], { ...d, unit_ids: [d.unit_id, ...(d.shared_unit_ids || [])].filter(Boolean) }, ({ unit_ids, ...data }) =>
      api(`/api/documents/${d.id}`, { method: "PUT", body: { ...data, unit_id: unit_ids[0] ?? null, shared_unit_ids: unit_ids.slice(1) } }));
    if (d.uploaded_at) {  // thông tin chỉ đọc: ai đăng, lúc nào (không cần sửa)
      $("#modal-body").insertAdjacentHTML("afterbegin", `<p class="muted">Người đăng: ${d.uploader_name ? uploaderHtml(d) : "không rõ"} · tải lên ${esc(String(d.uploaded_at).slice(0, 16))}</p>`);
    }
  }));
  el.querySelectorAll("[data-review-doc]").forEach((b) => (b.onclick = () => reviewDoc(b.dataset.reviewDoc, () => render())));
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
