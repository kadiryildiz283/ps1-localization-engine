/**
 * VirtualCDROM: 2352 bayt/sektör PS1 disk imajını tarayıcı RAM'ine tamamen yüklemeden
 * parça (chunk) veya HTTP Range istekleriyle talep üzerine okur.
 */
export class VirtualCDROM {
  constructor(manifest) {
    this.manifest = manifest;
    this.sectorSize = manifest.sector_size || 2352;
    this.cache = new Map(); // chunkIndex -> Uint8Array (LRU sınırlı)
    this.maxCachedChunks = 16;
    this.bytesFetched = 0;
  }

  async readSectors(startLba, count) {
    const out = new Uint8Array(count * this.sectorSize);
    if (this.manifest.mode === "chunked") {
      const spc = this.manifest.chunk_sectors;
      let offset = 0;
      let remaining = count;
      let lba = startLba;
      while (remaining > 0) {
        const chunkIdx = Math.floor(lba / spc);
        const inChunkLba = lba % spc;
        const take = Math.min(remaining, spc - inChunkLba);
        const chunkData = await this._getChunk(chunkIdx);
        const srcStart = inChunkLba * this.sectorSize;
        out.set(chunkData.subarray(srcStart, srcStart + take * this.sectorSize), offset);
        offset += take * this.sectorSize;
        lba += take;
        remaining -= take;
      }
      return out;
    }

    // Range modu: doğrudan HTTP Range isteği
    const startByte = startLba * this.sectorSize;
    const endByte = startByte + count * this.sectorSize - 1;
    const res = await fetch(this.manifest.disc_url, {
      headers: { Range: `bytes=${startByte}-${endByte}` },
    });
    if (!res.ok && res.status !== 206) {
      throw new Error(`HTTP Range hatası: ${res.status}`);
    }
    const buf = new Uint8Array(await res.arrayBuffer());
    this.bytesFetched += buf.byteLength;
    return buf;
  }

  async _getChunk(index) {
    if (this.cache.has(index)) {
      const hit = this.cache.get(index);
      this.cache.delete(index);
      this.cache.set(index, hit);
      return hit;
    }
    const entry = this.manifest.chunks[index];
    if (!entry) throw new Error(`Geçersiz chunk indeksi: ${index}`);
    const res = await fetch(entry.path);
    if (!res.ok) throw new Error(`Chunk indirilemedi: ${entry.path} (${res.status})`);
    const data = new Uint8Array(await res.arrayBuffer());
    this.bytesFetched += data.byteLength;

    if (this.cache.size >= this.maxCachedChunks) {
      const oldestKey = this.cache.keys().next().value;
      this.cache.delete(oldestKey);
    }
    this.cache.set(index, data);
    return data;
  }
}
