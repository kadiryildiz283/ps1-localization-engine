const stageEl = document.getElementById("stage");
const splashEl = document.getElementById("splash");
const titleEl = document.getElementById("game-title");
const subEl = document.getElementById("splash-sub");
const statusEl = document.getElementById("status");
const progressEl = document.getElementById("progress");
const playBtn = document.getElementById("play-btn");
const hudEl = document.getElementById("hud");
const pauseBtn = document.getElementById("pause-btn");
const saveBtn = document.getElementById("save-btn");
const loadBtn = document.getElementById("load-btn");
const padToggleBtn = document.getElementById("pad-toggle-btn");
const fsBtn = document.getElementById("fs-btn");
const touchPadEl = document.getElementById("touch-pad");
const biosInput = document.getElementById("bios-input");
const canvas = document.getElementById("screen");

let manifest = null;
let preloadedRom = null;
let nostalgist = null;
let paused = false;
let savedStateBlob = null;
let selectedBiosFile = null;

const isTouchDevice = () => window.matchMedia("(pointer: coarse)").matches || "ontouchstart" in window;

function setStatus(msg) {
  statusEl.textContent = msg;
}

function dispatchKey(type, key, code) {
  const ev = new KeyboardEvent(type, { key, code, bubbles: true, cancelable: true });
  window.dispatchEvent(ev);
  document.dispatchEvent(ev);
}

function setupTouchControls() {
  touchPadEl.classList.add("visible");

  padToggleBtn.addEventListener("click", () => {
    touchPadEl.classList.toggle("visible");
  });

  const activePointers = new Map(); // pointerId -> { btn, key, code }
  const releasePointer = (pid) => {
    const entry = activePointers.get(pid);
    if (!entry) return;
    entry.btn.classList.remove("active");
    dispatchKey("keyup", entry.key, entry.code);
    activePointers.delete(pid);
  };

  touchPadEl.querySelectorAll(".vbtn").forEach((btn) => {
    const key = btn.dataset.key;
    const code = btn.dataset.code;
    btn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      btn.setPointerCapture?.(e.pointerId);
      btn.classList.add("active");
      activePointers.set(e.pointerId, { btn, key, code });
      dispatchKey("keydown", key, code);
    });
    btn.addEventListener("pointerup", (e) => releasePointer(e.pointerId));
    btn.addEventListener("pointercancel", (e) => releasePointer(e.pointerId));
  });
}

biosInput.addEventListener("change", () => {
  selectedBiosFile = biosInput.files?.[0] || null;
  if (selectedBiosFile) setStatus(`BIOS seçildi: ${selectedBiosFile.name}`);
});

function mountRangeDiscFile(FS, dir, name, url, totalBytes) {
  FS.mkdirTree(dir);
  const node = FS.createDataFile(dir, name, new Uint8Array(0), true, false, false);
  const blockSize = 512 * 1024;
  const cache = new Map();
  const maxBlocks = 32;

  const getBlock = (idx) => {
    if (cache.has(idx)) {
      const hit = cache.get(idx);
      cache.delete(idx);
      cache.set(idx, hit);
      return hit;
    }
    const start = idx * blockSize;
    const end = Math.min(totalBytes - 1, start + blockSize - 1);
    const xhr = new XMLHttpRequest();
    xhr.open("GET", url, false);
    xhr.overrideMimeType("text/plain; charset=x-user-defined");
    xhr.setRequestHeader("Range", `bytes=${start}-${end}`);
    xhr.send(null);
    if (xhr.status !== 200 && xhr.status !== 206) {
      throw new Error(`Range HTTP ${xhr.status}`);
    }
    const txt = xhr.responseText || "";
    const bytes = new Uint8Array(txt.length);
    for (let i = 0; i < txt.length; i++) bytes[i] = txt.charCodeAt(i) & 0xff;
    if (cache.size >= maxBlocks) cache.delete(cache.keys().next().value);
    cache.set(idx, bytes);
    return bytes;
  };

  const origGetAttr = node.node_ops.getattr;
  node.node_ops = {
    ...node.node_ops,
    getattr(n) {
      const attr = origGetAttr(n);
      attr.size = totalBytes;
      return attr;
    },
  };

  node.stream_ops = {
    ...node.stream_ops,
    llseek(stream, offset, whence) {
      let pos = offset;
      if (whence === 1) pos += stream.position;
      else if (whence === 2) pos += totalBytes;
      if (pos < 0) throw new FS.ErrnoError(28);
      return pos;
    },
    read(stream, buffer, offset, length, position) {
      const pos = position !== undefined ? position : stream.position;
      if (pos >= totalBytes || length <= 0) return 0;
      const toRead = Math.min(length, totalBytes - pos);
      let readSoFar = 0;
      while (readSoFar < toRead) {
        const cur = pos + readSoFar;
        const blkIdx = Math.floor(cur / blockSize);
        const inBlk = cur % blockSize;
        const blk = getBlock(blkIdx);
        const take = Math.min(toRead - readSoFar, blk.length - inBlk);
        if (take <= 0) break;
        buffer.set(blk.subarray(inBlk, inBlk + take), offset + readSoFar);
        readSoFar += take;
      }
      if (position === undefined) stream.position += readSoFar;
      return readSoFar;
    },
  };
}

async function preloadDisc() {
  const cueRes = await fetch(manifest.cue_url || "./disc.cue");
  const cueBlob = new Blob([await cueRes.text()], { type: "text/plain" });

  if (manifest.mode === "range") {
    progressEl.value = 100;
    return [{ fileName: "disc.cue", fileContent: cueBlob }];
  }

  const total = manifest.chunks.length;
  const parts = new Array(total);
  progressEl.max = total;
  progressEl.value = 0;

  for (let i = 0; i < total; i++) {
    const entry = manifest.chunks[i];
    setStatus(`Oyun indiriliyor... %${Math.round(((i + 1) / total) * 100)}`);
    const res = await fetch(entry.path);
    if (!res.ok) throw new Error(`Parça indirilemedi: ${entry.path} (${res.status})`);
    parts[i] = await res.arrayBuffer();
    progressEl.value = i + 1;
  }

  const binBlob = new Blob(parts, { type: "application/octet-stream" });
  return [
    { fileName: "disc.cue", fileContent: cueBlob },
    { fileName: "disc.bin", fileContent: binBlob },
  ];
}

async function enterFullscreenLandscape() {
  try {
    if (!document.fullscreenElement && stageEl.requestFullscreen) {
      await stageEl.requestFullscreen();
    }
    if (screen.orientation?.lock) {
      await screen.orientation.lock("landscape").catch(() => {});
    }
  } catch {
    // Masaüstü veya iOS Safari tam ekran kısıtı sessizce yok sayılır
  }
}

async function startGame() {
  if (typeof window.Nostalgist === "undefined") {
    setStatus("Nostalgist.js yüklenemedi (internet/CDN bağlantısı gerekli).");
    return;
  }
  playBtn.disabled = true;
  if (isTouchDevice()) await enterFullscreenLandscape();

  setStatus("PS1 WASM çekirdeği başlatılıyor...");
  const launchOpts = {
    core: "pcsx_rearmed",
    rom: preloadedRom,
    element: canvas,
    style: {
      position: "static",
      width: "min(100vw, calc(100dvh * 4 / 3))",
      height: "min(100dvh, calc(100vw * 3 / 4))",
    },
    retroarchConfig: {
      audio_latency: 160,
      audio_rate_control: true,
      audio_rate_control_delta: 0.005,
    },
    cache: { core: true, rom: false, bios: true },
  };
  if (selectedBiosFile) {
    launchOpts.bios = [selectedBiosFile];
  } else if (manifest.bios_bin) {
    launchOpts.bios = [manifest.bios_bin];
  }
  if (manifest.core_wasm) {
    launchOpts.resolveCoreWasm = () => manifest.core_wasm;
  }

  if (manifest.mode === "range") {
    const discUrl = new URL(manifest.disc_url, window.location.href).href;
    launchOpts.beforeLaunch = (instance) => {
      const FS = instance.getEmscriptenFS();
      mountRangeDiscFile(
        FS,
        "/home/web_user/retroarch/userdata/content",
        "disc.bin",
        discUrl,
        manifest.total_bytes
      );
    };
  }

  nostalgist = await window.Nostalgist.launch(launchOpts);
  splashEl.classList.add("hidden");
  hudEl.classList.remove("hidden");
  paused = false;
}

playBtn.addEventListener("click", () => {
  startGame().catch((err) => {
    console.error("ps1towasm launch error:", err);
    const detail = err?.message || (err?.errno !== undefined ? `FS errno ${err.errno}` : String(err));
    setStatus(`Başlatma hatası: ${detail}`);
    playBtn.disabled = false;
  });
});

pauseBtn.addEventListener("click", () => {
  if (!nostalgist) return;
  if (paused) {
    nostalgist.resume();
    paused = false;
    pauseBtn.textContent = "⏸";
  } else {
    nostalgist.pause();
    paused = true;
    pauseBtn.textContent = "▶";
  }
});

saveBtn.addEventListener("click", async () => {
  if (!nostalgist) return;
  const { state } = await nostalgist.saveState();
  savedStateBlob = state;
  saveBtn.textContent = "✓";
  setTimeout(() => (saveBtn.textContent = "💾"), 1000);
});

loadBtn.addEventListener("click", async () => {
  if (!nostalgist || !savedStateBlob) return;
  await nostalgist.loadState(savedStateBlob);
});

fsBtn.addEventListener("click", () => {
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  } else {
    enterFullscreenLandscape();
  }
});

async function init() {
  setupTouchControls();
  const res = await fetch("./manifest.json");
  manifest = await res.json();
  titleEl.textContent = manifest.volume_id || "PS1toWASM";
  subEl.textContent = `${manifest.boot_exe || "PS1"} • ${(manifest.total_bytes / 1048576).toFixed(0)} MiB`;

  preloadedRom = await preloadDisc();
  setStatus("Hazır! Başlamak için dokunun.");
  playBtn.disabled = false;
}

init().catch((err) => setStatus(`Hata: ${err.message}`));
