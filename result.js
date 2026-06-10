const params = new URLSearchParams(window.location.search);
const resultId = params.get("id");
const error = params.get("error");
const loadingState = document.querySelector("#loadingState");
const errorState = document.querySelector("#errorState");
const reportPage = document.querySelector("#reportPage");
const errorMessage = document.querySelector("#errorMessage");

const scoreLabels = {
  selfDisplay: "자기표현",
  relationSensitivity: "관계 민감도",
  emotionalDepth: "감정 깊이",
  approvalNeed: "인정 욕구",
  distanceControl: "거리 조절",
  shadowIndex: "그림자 지수"
};

function showError(message) {
  loadingState.hidden = true;
  reportPage.hidden = true;
  errorState.hidden = false;
  errorMessage.textContent = message || "분석 결과를 불러오지 못했습니다.";
}

function number(value) {
  if (value === null || value === undefined || value === "") return "-";
  return Number(value).toLocaleString("ko-KR");
}

function renderResult(result) {
  loadingState.hidden = true;
  errorState.hidden = true;
  reportPage.hidden = false;

  const profile = result.profile || {};
  const evidence = result.evidence || {};
  const archetype = result.archetype || {};

  document.querySelector("#archetypeName").textContent = archetype.name || "무의식 유형";
  document.querySelector("#archetypeSubtitle").textContent = archetype.subtitle || "Instagram 데이터 기반 분석";
  document.querySelector("#summaryText").textContent = archetype.summary || "";
  document.querySelector("#username").textContent = `@${profile.username || result.payload?.handle || "instagram"}`;
  document.querySelector("#profileMeta").textContent = [
    profile.accountType || "Professional",
    profile.followersCount ? `팔로워 ${number(profile.followersCount)}` : "",
    profile.mediaCount ? `게시물 ${number(profile.mediaCount)}` : ""
  ].filter(Boolean).join(" · ");
  document.querySelector("#typeCardTitle").textContent = (archetype.name || "무의식").split(" ").slice(-1)[0];

  const image = document.querySelector("#profileImage");
  if (profile.profilePictureUrl) {
    image.src = profile.profilePictureUrl;
    image.hidden = false;
  }

  document.querySelector("#mediaAnalyzed").textContent = number(evidence.mediaAnalyzed);
  document.querySelector("#commentsAnalyzed").textContent = number(evidence.commentsAnalyzed);
  document.querySelector("#uniqueCommenters").textContent = number(evidence.uniqueCommenters);
  document.querySelector("#totalReactions").textContent = number((evidence.totalLikes || 0) + (evidence.declaredComments || 0));

  const scoreGrid = document.querySelector("#scoreGrid");
  scoreGrid.innerHTML = "";
  Object.entries(result.scores || {}).forEach(([key, value]) => {
    const item = document.createElement("div");
    item.className = "score-item";
    item.innerHTML = `
      <span>${scoreLabels[key] || key}</span>
      <div class="score-track"><i style="width:${Math.max(4, Math.min(100, value))}%"></i></div>
      <strong>${value}</strong>
    `;
    scoreGrid.appendChild(item);
  });

  const chapterList = document.querySelector("#chapterList");
  chapterList.innerHTML = "";
  (result.chapters || []).forEach((chapter, index) => {
    const card = document.createElement("article");
    card.className = "chapter-card";
    card.innerHTML = `
      <h3>${index + 1}. ${chapter.title}</h3>
      <p>${chapter.body}</p>
    `;
    chapterList.appendChild(card);
  });

  const keywordGrid = document.querySelector("#keywordGrid");
  keywordGrid.innerHTML = "";
  const topWords = evidence.topWords || [];
  const topCommenters = evidence.topCommenters || [];
  [...topWords.slice(0, 10).map(([word, count]) => `${word} ${count}`), ...topCommenters.slice(0, 5).map(([name, count]) => `@${name} ${count}`)].forEach((label) => {
    const chip = document.createElement("span");
    chip.textContent = label;
    keywordGrid.appendChild(chip);
  });
  if (!keywordGrid.children.length) {
    const chip = document.createElement("span");
    chip.textContent = "분석 가능한 텍스트 신호가 적습니다";
    keywordGrid.appendChild(chip);
  }

  document.querySelector("#disclaimer").textContent = result.disclaimer || "";
}

async function loadResult() {
  if (error) {
    showError(error);
    return;
  }
  if (!resultId) {
    showError("결과 ID가 없습니다. 처음부터 다시 분석해 주세요.");
    return;
  }

  try {
    const response = await fetch(`/api/result/${resultId}`);
    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "결과를 찾을 수 없습니다.");
      return;
    }
    renderResult(data);
  } catch (loadError) {
    showError("Python 분석 서버에 연결할 수 없습니다.");
  }
}

loadResult();
