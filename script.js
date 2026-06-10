const startForm = document.querySelector("#startForm");
const bottomForm = document.querySelector("#bottomForm");
const handleInput = document.querySelector("#handleInput");
const bottomHandleInput = document.querySelector("#bottomHandleInput");
const mainCta = document.querySelector("#mainCta");
const accountModal = document.querySelector("#accountModal");
const specialModal = document.querySelector("#specialModal");
const profileModal = document.querySelector("#profileModal");
const analysisOverlay = document.querySelector("#analysisOverlay");
const analysisOverlayTitle = document.querySelector("#analysisOverlayTitle");
const analysisStatus = document.querySelector("#analysisStatus");
const progressFill = document.querySelector("#progressFill");
const closeAnalysis = document.querySelector("#closeAnalysis");
const specialStart = document.querySelector("#specialStart");
const profileStart = document.querySelector("#profileStart");
const skipProfile = document.querySelector("#skipProfile");
const birthYear = document.querySelector("#birthYear");
const customQuestion = document.querySelector("#customQuestion");
const analysisCount = document.querySelector("#analysisCount");

const state = {
  handle: "",
  accountType: "",
  question: "나를 무장해제 시키는 칭찬 세가지는?",
  gender: "",
  year: "",
  progressTimer: null
};

const statuses = [
  "계정 접근 가능 여부를 확인하는 중입니다.",
  "최근 게시물의 색감과 구도를 분류하는 중입니다.",
  "캡션의 말투와 반복되는 단어를 해석하는 중입니다.",
  "댓글과 관계 신호를 교차 분석하는 중입니다.",
  "무의식 유형 후보를 좁히는 중입니다.",
  "스페셜 질문 리포트 챕터를 생성하는 중입니다."
];

function apiBase() {
  return window.INSTAGRAM_ANALYSIS_API_BASE || "";
}

function normalizeHandle(value) {
  return value.trim().replace(/^@+/, "").replace(/\s+/g, "");
}

function syncHandleFromBottom() {
  const bottom = normalizeHandle(bottomHandleInput.value);
  if (bottom) handleInput.value = bottom;
}

function openModal(modal) {
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeModals() {
  for (const modal of [accountModal, specialModal, profileModal]) {
    modal.setAttribute("aria-hidden", "true");
  }
  document.body.classList.remove("modal-open");
}

function requestStart(event) {
  event.preventDefault();
  if (event.currentTarget === bottomForm) syncHandleFromBottom();

  const handle = normalizeHandle(handleInput.value);
  if (!handle || handle.length < 2) {
    handleInput.focus();
    handleInput.animate(
      [
        { transform: "translateX(0)" },
        { transform: "translateX(-7px)" },
        { transform: "translateX(7px)" },
        { transform: "translateX(0)" }
      ],
      { duration: 220, iterations: 1 }
    );
    return;
  }

  state.handle = handle;
  openModal(accountModal);
}

function chooseAccount(event) {
  const target = event.target.closest("[data-account]");
  if (!target) return;
  state.accountType = target.dataset.account;
  closeModals();
  openModal(specialModal);
}

function chooseQuestion(event) {
  const option = event.target.closest(".question-option");
  if (!option) return;

  document.querySelectorAll(".question-option").forEach((button) => button.classList.remove("selected"));
  option.classList.add("selected");
  state.question = option.textContent.trim();

  if (state.question.includes("직접")) {
    customQuestion.classList.add("visible");
    customQuestion.focus();
  } else {
    customQuestion.classList.remove("visible");
  }
}

function chooseGender(event) {
  const button = event.target.closest("[data-gender]");
  if (!button) return;
  document.querySelectorAll("[data-gender]").forEach((item) => item.classList.remove("selected"));
  button.classList.add("selected");
  state.gender = button.dataset.gender;
}

function openProfileStep() {
  if (customQuestion.classList.contains("visible") && customQuestion.value.trim()) {
    state.question = customQuestion.value.trim();
  }
  closeModals();
  openModal(profileModal);
}

async function startAnalysis() {
  state.year = birthYear.value;
  closeModals();
  document.body.classList.add("analysis-open");
  analysisOverlay.setAttribute("aria-hidden", "false");
  analysisOverlayTitle.textContent = `@${state.handle} 분석을 시작했습니다`;
  progressFill.style.width = "6%";
  analysisStatus.textContent = "실제 Instagram Login 연결을 준비하는 중입니다.";
  mainCta.textContent = "분석 중...";

  try {
    const response = await fetch(`${apiBase()}/api/analysis/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        handle: state.handle,
        accountType: state.accountType,
        question: state.question,
        gender: state.gender,
        birthYear: state.year
      })
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      showBackendSetup(data);
      return;
    }

    if (data.mode === "setup_required") {
      showBackendSetup(data);
      return;
    }

    if (data.authUrl) {
      progressFill.style.width = "38%";
      analysisStatus.textContent = "Instagram 권한 동의 화면으로 이동합니다.";
      setTimeout(() => {
        window.location.href = data.authUrl;
      }, 700);
      return;
    }

    showBackendSetup({ message: "분석 서버 응답에 authUrl이 없습니다." });
  } catch (error) {
    showBackendSetup({
      message: "Python 분석 서버에 연결할 수 없습니다. 로컬에서는 `python app.py`로 실행해야 실제 분석이 가능합니다."
    });
  }
}

function runProgress() {
  clearInterval(state.progressTimer);
  let progress = 6;
  let index = 0;
  const steps = [...document.querySelectorAll(".analysis-steps li")];
  steps.forEach((step, i) => step.classList.toggle("active", i === 0));

  state.progressTimer = setInterval(() => {
    progress = Math.min(96, progress + 4 + Math.round(Math.random() * 7));
    const nextIndex = Math.min(statuses.length - 1, Math.floor(progress / 18));
    if (nextIndex !== index) {
      index = nextIndex;
      analysisStatus.textContent = statuses[index];
      steps.forEach((step, stepIndex) => step.classList.toggle("active", stepIndex <= Math.min(stepIndex, Math.floor(progress / 25))));
    }
    progressFill.style.width = `${progress}%`;
    if (progress >= 96) {
      clearInterval(state.progressTimer);
      analysisStatus.textContent = "분석 서버에 접수되었습니다. 리포트 미리보기를 준비하고 있습니다.";
    }
  }, 620);
}

function showBackendSetup(data) {
  clearInterval(state.progressTimer);
  progressFill.style.width = "100%";
  analysisOverlayTitle.textContent = "실제 분석 서버 설정이 필요합니다";
  analysisStatus.innerHTML = [
    data?.message || "Instagram API 앱 설정이 필요합니다.",
    "`.env`에 IG_APP_ID, IG_APP_SECRET, IG_REDIRECT_URI를 넣고 Python 서버로 실행하세요.",
    "정적 GitHub Pages만으로는 실제 Instagram token을 안전하게 받을 수 없습니다."
  ].join("<br>");
  document.querySelectorAll(".analysis-steps li").forEach((step, index) => {
    step.classList.toggle("active", index === 0);
  });
}

function closeAnalysisOverlay() {
  analysisOverlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("analysis-open");
}

function animateCount() {
  const target = 888514;
  const start = 327119;
  const duration = 1200;
  const started = performance.now();

  function tick(now) {
    const progress = Math.min(1, (now - started) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.floor(start + (target - start) * eased);
    analysisCount.textContent = value.toLocaleString("ko-KR");
    if (progress < 1) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

function wireFaq() {
  document.querySelectorAll(".faq-item").forEach((item) => {
    item.addEventListener("click", () => {
      item.classList.toggle("open");
    });
  });
}

function wireScrollCtas() {
  document.querySelectorAll("[data-scroll-start]").forEach((button) => {
    button.addEventListener("click", () => {
      handleInput.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => handleInput.focus(), 450);
    });
  });
}

startForm.addEventListener("submit", requestStart);
bottomForm.addEventListener("submit", requestStart);
accountModal.addEventListener("click", chooseAccount);
specialModal.addEventListener("click", chooseQuestion);
profileModal.addEventListener("click", chooseGender);
specialStart.addEventListener("click", openProfileStep);
profileStart.addEventListener("click", startAnalysis);
skipProfile.addEventListener("click", startAnalysis);
closeAnalysis.addEventListener("click", closeAnalysisOverlay);
birthYear.addEventListener("change", () => {
  state.year = birthYear.value;
});

document.addEventListener("click", (event) => {
  if (event.target.matches("[data-close-modal]")) {
    closeModals();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeModals();
    closeAnalysisOverlay();
  }
});

wireFaq();
wireScrollCtas();
animateCount();
