const analyzeBtn = document.getElementById("analyze-btn");
const keywordBtn = document.getElementById("keyword-analyze-btn");
const urlInput = document.getElementById("url-input");
const keywordInput = document.getElementById("keyword-input");
const statusText = document.getElementById("status-text");
const keywordStatus = document.getElementById("keyword-status");
const progressBar = document.getElementById("progress-bar");
const totalSpikeList = document.getElementById("total-spike-list");
const keywordSpikeList = document.getElementById("keyword-spike-list");
const totalCanvas = document.getElementById("total-chart");
const keywordCanvas = document.getElementById("keyword-chart");
const DEFAULT_Y_MAX = 10; // CPSの最低縦軸上限
const Y_PADDING_RATIO = 0.2;

let totalChart;
let keywordChart;
let pollHandle = null;
let currentJobId = null;

async function analyze() {
  if (!urlInput.value) {
    alert("URLを入力してください");
    return;
  }
  resetResults();
  analyzeBtn.disabled = true;
  keywordBtn.disabled = true;
  setStatus("解析ジョブを開始しています...");
  setProgressActive(true);
  try {
    const response = await fetch("/analyze/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: urlInput.value }),
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || "ジョブの開始に失敗しました");
    }
    const data = await response.json();
    startPolling(data.job_id);
  } catch (error) {
    setStatus(error.message);
    analyzeBtn.disabled = false;
    setProgressActive(false);
  }
}

function resetResults() {
  currentJobId = null;
  destroyChart(totalChart);
  destroyChart(keywordChart);
  totalChart = undefined;
  keywordChart = undefined;
  totalSpikeList.innerHTML = "";
  keywordSpikeList.innerHTML = "";
  keywordStatus.textContent = "キーワード未解析";
}

function startPolling(jobId) {
  if (pollHandle) {
    clearInterval(pollHandle);
  }
  pollHandle = setInterval(() => fetchStatus(jobId), 2000);
  fetchStatus(jobId);
}

async function fetchStatus(jobId) {
  try {
    const response = await fetch(`/analyze/status/${jobId}`);
    if (!response.ok) {
      throw new Error("進捗の取得に失敗しました");
    }
    const data = await response.json();
    handleStatus(data);
  } catch (error) {
    setStatus(error.message);
    stopPolling();
    analyzeBtn.disabled = false;
    setProgressActive(false);
  }
}

function handleStatus(job) {
  if (job.status === "running" || job.status === "queued") {
    const processed = job.processed_messages || 0;
    const timestamp = job.last_timestamp ? `${job.last_timestamp.toFixed(1)}s` : "-";
    setStatus(`解析中: ${processed}件処理済み (最新タイムスタンプ ${timestamp})`);
    setProgressActive(true);
  } else if (job.status === "completed") {
    stopPolling();
    currentJobId = job.job_id;
    setStatus("全コメントの解析が完了しました");
    if (job.result_total) {
      renderTotalSection(job.result_total);
    }
    if (job.result_keyword && job.keyword) {
      renderKeywordSection(job.result_keyword, job.keyword);
    } else {
      keywordStatus.textContent = "キーワード未解析";
    }
    analyzeBtn.disabled = false;
    keywordBtn.disabled = false;
    setProgressActive(false);
  } else if (job.status === "error") {
    stopPolling();
    setStatus(job.error || "解析に失敗しました");
    analyzeBtn.disabled = false;
    setProgressActive(false);
  }
}

function setStatus(message) {
  statusText.textContent = message;
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
}

function setProgressActive(active) {
  progressBar.classList.toggle("active", active);
  progressBar.style.width = active ? "100%" : "0%";
}

function renderTotalSection(result) {
  const series = result.series;
  renderLineChart(
    totalCanvas,
    "全コメント (スムージング)",
    series.time_axis,
    series.smoothed_total,
    "#111",
    "total"
  );
  renderSpikes(totalSpikeList, result.spikes);
}

function renderKeywordSection(result, keyword) {
  keywordStatus.textContent = `「${keyword}」の結果`;
  const series = result.series;
  renderLineChart(
    keywordCanvas,
    `キーワード (${keyword})`,
    series.time_axis,
    series.smoothed_keyword && series.smoothed_keyword.length
      ? series.smoothed_keyword
      : series.keyword,
    "#00c48c",
    "keyword"
  );
  renderSpikes(keywordSpikeList, result.spikes);
}

function renderLineChart(canvas, label, labels, data, color, type) {
  destroyChart(type === "total" ? totalChart : keywordChart);
  const yMax = computeYMax(data);
  const chartInstance = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label,
          data,
          borderColor: color,
          borderWidth: 2,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { title: { display: true, text: "秒" } },
        y: {
          title: { display: true, text: "CPS" },
          min: 0,
          suggestedMax: yMax,
          max: yMax,
          beginAtZero: true,
        },
      },
    },
  });
  if (type === "total") {
    totalChart = chartInstance;
  } else {
    keywordChart = chartInstance;
  }
}

function destroyChart(chartInstance) {
  if (chartInstance) {
    chartInstance.destroy();
  }
}

function computeYMax(data) {
  if (!data || !data.length) {
    return DEFAULT_Y_MAX;
  }
  const maxVal = Math.max(...data);
  if (maxVal <= 0) {
    return DEFAULT_Y_MAX;
  }
  const padded = maxVal * (1 + Y_PADDING_RATIO);
  const rounded = Math.ceil(padded / 5) * 5;
  return Math.max(rounded, DEFAULT_Y_MAX);
}

function renderSpikes(listElement, spikes) {
  if (!spikes || !spikes.length) {
    listElement.innerHTML = "<li>しきい値を超えるスパイクはありませんでした。</li>";
    return;
  }
  listElement.innerHTML = "";
  spikes.forEach((spike) => {
    const item = document.createElement("li");
    item.innerHTML = `開始 ${spike.start_time.toFixed(
      1
    )}s / ピーク ${spike.peak_time.toFixed(1)}s (CPS ${spike.peak_value.toFixed(
      2
    )}) → <a href="${spike.jump_url}" target="_blank">視聴</a>`;
    listElement.appendChild(item);
  });
}

async function analyzeKeyword() {
  if (!currentJobId) {
    alert("先に配信URLの解析を実行してください");
    return;
  }
  const keyword = keywordInput.value.trim();
  if (!keyword) {
    keywordStatus.textContent = "キーワードを入力してください";
    return;
  }
  keywordBtn.disabled = true;
  keywordStatus.textContent = "キーワード解析中...";
  try {
    const response = await fetch(`/analyze/recompute/${currentJobId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword }),
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || "キーワード解析に失敗しました");
    }
    const data = await response.json();
    renderKeywordSection(data.result, keyword);
  } catch (error) {
    keywordStatus.textContent = error.message;
  } finally {
    keywordBtn.disabled = false;
  }
}

analyzeBtn.addEventListener("click", analyze);
keywordBtn.addEventListener("click", analyzeKeyword);
