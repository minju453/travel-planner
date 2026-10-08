// ==========================================================================
// AI 여행 플래너 클라이언트 스크립트 (Flight Ticket & Scrapbook Theme)
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("plannerForm");
  const submitBtn = document.getElementById("submitBtn");
  const emptyState = document.getElementById("emptyState");
  const loadingState = document.getElementById("loadingState");
  const errorAlert = document.getElementById("errorAlert");
  const errorMessage = document.getElementById("errorMessage");
  const resultContent = document.getElementById("resultContent");
  const imageGallery = document.getElementById("imageGallery");
  const actionButtons = document.getElementById("actionButtons");
  const copyBtn = document.getElementById("copyBtn");
  const downloadBtn = document.getElementById("downloadBtn");

  // 티켓 텍스트 엘리먼트
  const ticketDestDisplay = document.getElementById("ticketDestDisplay");
  const ticketStubDest = document.getElementById("ticketStubDest");
  const destinationInput = document.getElementById("destination");

  // 마지막으로 생성된 원본 마크다운 텍스트 저장용 변수
  let currentRawPlan = "";
  let currentDestination = "여행일정";

  // 여행지 입력창 입력 시 티켓에 실시간 반영되는 재미요소
  destinationInput.addEventListener("input", (e) => {
    const val = e.target.value.trim();
    if (val) {
      ticketDestDisplay.textContent = val;
      ticketStubDest.textContent = val.toUpperCase();
    } else {
      ticketDestDisplay.textContent = "당신의 여행지";
      ticketStubDest.textContent = "DESTINATION";
    }
  });

  // 에러 메시지 표시 헬퍼 함수
  const showError = (msg) => {
    errorMessage.textContent = msg;
    errorAlert.style.display = "flex";
    loadingState.style.display = "none";
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span class="btn-text">✈️ 여행 플랜 발권하기</span>';
  };

  // 에러 숨김 헬퍼 함수
  const hideError = () => {
    errorAlert.style.display = "none";
    errorMessage.textContent = "";
  };

  // 폴라로이드 사진 갤러리 렌더링 함수
  const renderGallery = (images) => {
    imageGallery.innerHTML = "";
    if (!images || images.length === 0) {
      imageGallery.style.display = "none";
      return;
    }

    images.forEach((img) => {
      const card = document.createElement("div");
      card.className = "polaroid-card";

      const imageEl = document.createElement("img");
      imageEl.src = img.url;
      imageEl.alt = img.title || "여행지 사진";
      imageEl.loading = "lazy";
      // 이미지 로딩 실패 시 카드 숨김
      imageEl.onerror = () => {
        card.style.display = "none";
      };

      const caption = document.createElement("div");
      caption.className = "polaroid-caption";
      caption.textContent = img.title || "Travel Moment";

      card.appendChild(imageEl);
      card.appendChild(caption);
      imageGallery.appendChild(card);
    });

    imageGallery.style.display = "grid";
  };

  // 1. 폼 제출 이벤트 처리
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    // 입력값 추출
    const destination = destinationInput.value.trim();
    const duration = document.getElementById("duration").value.trim();
    const budget = document.getElementById("budget").value.trim();
    const interests = document.getElementById("interests").value.trim();
    const companions = document.getElementById("companions").value.trim();
    const transportation = document.getElementById("transportation").value;
    const accommodation = document.getElementById("accommodation").value;

    // 프론트엔드 유효성 검증
    if (!destination || !duration || !budget || !interests || !companions || !transportation || !accommodation) {
      showError("모든 필수 입력 항목(*)을 입력해 주세요.");
      return;
    }

    currentDestination = destination;
    ticketDestDisplay.textContent = destination;
    ticketStubDest.textContent = destination.toUpperCase();

    // UI 상태 전환: 로딩 시작
    emptyState.style.display = "none";
    resultContent.style.display = "none";
    imageGallery.style.display = "none";
    actionButtons.style.display = "none";
    loadingState.style.display = "block";
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="btn-text">⏳ 탑승권 발권 중...</span>';

    try {
      // Flask 백엔드 비동기 요청 (Fetch API)
      const response = await fetch("/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          destination,
          duration,
          budget,
          interests,
          companions,
          transportation,
          accommodation
        })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "일정 생성에 실패했습니다. 다시 시도해 주세요.");
      }

      // 결과 보관
      currentRawPlan = data.plan;

      // 폴라로이드 사진 렌더링
      renderGallery(data.images || []);

      // 마크다운 HTML 변환 및 화면 표시
      resultContent.innerHTML = marked.parse(currentRawPlan);

      // UI 상태 전환: 결과 화면 표시
      loadingState.style.display = "none";
      resultContent.style.display = "block";
      actionButtons.style.display = "flex";

    } catch (err) {
      showError(err.message || "서버 통신 중 알 수 없는 오류가 발생했습니다.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span class="btn-text">✈️ 여행 플랜 발권하기</span>';
    }
  });

  // 2. 전체 복사 버튼 기능
  copyBtn.addEventListener("click", async () => {
    if (!currentRawPlan) return;

    try {
      await navigator.clipboard.writeText(currentRawPlan);
      const originalText = copyBtn.textContent;
      copyBtn.textContent = "✅ 복사 완료!";
      copyBtn.disabled = true;

      setTimeout(() => {
        copyBtn.textContent = originalText;
        copyBtn.disabled = false;
      }, 2000);
    } catch (err) {
      alert("클립보드 복사에 실패했습니다. 브라우저 권한을 확인하세요.");
    }
  });

  // 3. Markdown (.md) 파일 다운로드 기능
  downloadBtn.addEventListener("click", () => {
    if (!currentRawPlan) return;

    const blob = new Blob([currentRawPlan], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    
    const safeName = currentDestination.replace(/[^a-zA-Z0-9가-힣]/g, "_");
    link.href = url;
    link.download = `${safeName}_여행일정.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  });
});
