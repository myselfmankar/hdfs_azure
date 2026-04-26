const $ = sel => document.querySelector(sel);
const logEl = $("#log");
const filesEl = $("#files tbody");
let currentSseFileId = null;

function human(n) {
  for (const u of ["B","KB","MB","GB"]) {
    if (n < 1024) return n.toFixed(1) + " " + u;
    n /= 1024;
  }
  return n.toFixed(1) + " TB";
}

function logLine({ts, msg}, cls="") {
  const span = document.createElement("span");
  span.className = "log-line " + cls;
  span.innerHTML = `<span class="ts">${ts}</span>${msg.replace(/</g,"&lt;")}\n`;
  logEl.appendChild(span);
  logEl.scrollTop = logEl.scrollHeight;
}

function classify(msg) {
  if (/^===/.test(msg)) return "phase";
  if (/^ERROR/.test(msg)) return "err";
  if (/COMPLETE|OK\b/.test(msg)) return "ok";
  return "";
}

async function refreshFiles() {
  const r = await fetch("/api/files");
  const items = await r.json();
  filesEl.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td title="${it.file_id}">${it.filename}</td>
      <td>${human(it.size)}</td>
      <td>${it.blocks}</td>
      <td class="actions">
        <button data-act="dl"  data-id="${it.file_id}">download</button>
        <button data-act="wc"  data-id="${it.file_id}" data-name="${it.filename}">word count</button>
        <button data-act="del" data-id="${it.file_id}" class="danger">delete</button>
      </td>`;
    filesEl.appendChild(tr);
  }
}

filesEl.addEventListener("click", async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = b.dataset.id;
  if (b.dataset.act === "dl")  window.location = `/api/download/${id}`;
  if (b.dataset.act === "del") {
    if (!confirm("Delete this file from HDFS?")) return;
    await fetch(`/api/files/${id}`, { method: "DELETE" });
    refreshFiles();
  }
  if (b.dataset.act === "wc") {
    $("#wc-card").hidden = false;
    $("#wc-card").dataset.fileId = id;
    $("#wc-target-file").textContent = "· " + b.dataset.name;
    $("#wc-result").innerHTML = "";
    $("#wc-card").scrollIntoView({behavior:"smooth", block:"nearest"});
  }
});

function streamJob(jobId, onResult) {
  $("#job-id").textContent = "job " + jobId.slice(0,8);
  logEl.innerHTML = "";
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  es.onmessage = ev => {
    const d = JSON.parse(ev.data);
    if (d.msg === "__done__") {
      es.close();
      logLine({ts: d.ts, msg: "(stream closed)"}, "phase");
      onResult && onResult(d.result);
      refreshFiles();
      return;
    }
    logLine(d, classify(d.msg));
  };
  es.onerror = () => { es.close(); logLine({ts:"--:--:--", msg:"(connection lost)"}, "err"); };
}

// upload --------------------------------------------------------
async function doUpload(file) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  const { job_id } = await r.json();
  streamJob(job_id);
}

const dz = $("#dropzone");
dz.addEventListener("click", () => $("#file").click());
$("#pick").addEventListener("click", e => { e.preventDefault(); $("#file").click(); });
$("#file").addEventListener("change", e => e.target.files[0] && doUpload(e.target.files[0]));
["dragenter","dragover"].forEach(t => dz.addEventListener(t, e => { e.preventDefault(); dz.classList.add("over"); }));
["dragleave","drop"].forEach(t => dz.addEventListener(t, e => { e.preventDefault(); dz.classList.remove("over"); }));
dz.addEventListener("drop", e => e.dataTransfer.files[0] && doUpload(e.dataTransfer.files[0]));

// word count ----------------------------------------------------
$("#wc-run").addEventListener("click", async () => {
  const fileId = $("#wc-card").dataset.fileId;
  const body = {
    file_id: fileId,
    target_word: $("#wc-word").value || null,
    top_n: parseInt($("#wc-topn").value, 10),
  };
  $("#wc-result").innerHTML = "";
  const r = await fetch("/api/jobs/wordcount", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  const { job_id } = await r.json();
  streamJob(job_id, renderWcResult);
});

function renderWcResult(res) {
  if (!res || res.error) {
    $("#wc-result").innerHTML = `<div class="target err">error: ${res && res.error}</div>`;
    return;
  }
  const max = res.top.length ? res.top[0].count : 1;
  const bars = res.top.map(({word,count}) => `
    <div class="bar">
      <div class="word">${word}</div>
      <div class="fill" style="width:${(count/max*240).toFixed(1)}px"></div>
      <div class="count">${count}</div>
    </div>`).join("");
  const tgt = res.target_word
    ? `<div class="target">count of <code>"${res.target_word}"</code> = <b>${res.target_count}</b></div>`
    : "";
  $("#wc-result").innerHTML = `
    ${tgt}
    <div style="color:var(--muted);font-size:12px;margin-bottom:6px">
      ${res.total_tokens.toLocaleString()} tokens · ${res.unique_tokens.toLocaleString()} unique ·
      ${res.blocks_processed} blocks
    </div>
    ${bars}`;
}

// init ----------------------------------------------------------
fetch("/api/health").then(r => r.json()).then(j => {
  $("#cluster-status").textContent = j.status === "ok" ? "online" : "down";
  $("#cluster-status").className = j.status === "ok" ? "ok" : "bad";
}).catch(() => { $("#cluster-status").textContent = "down"; $("#cluster-status").className = "bad"; });

refreshFiles();
