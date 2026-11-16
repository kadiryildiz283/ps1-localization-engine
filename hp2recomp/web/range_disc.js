/* HTTP Range backed lazy file for the hp2_web build (issue #7).
 *
 * Mounts a large host file (the 715 MB disc .bin) into MEMFS without
 * downloading it: reads are satisfied by synchronous XHR Range requests
 * against a 512 KiB LRU block cache. std::ifstream consumers (iso_reader)
 * see an ordinary file at the given MEMFS path.
 *
 * Model: ps1towasm/web/runtime.js mountRangeDiscFile (same repo).
 */

function ps1MountRangeFile(url, memfsPath, totalBytes) {
  var FS = Module.FS;
  var slash = memfsPath.lastIndexOf("/");
  var dir = slash > 0 ? memfsPath.slice(0, slash) : "/";
  var name = memfsPath.slice(slash + 1);
  FS.mkdirTree(dir);
  FS.createDataFile(dir, name, new Uint8Array(0), true, false, false);
  /* Emscripten 7 createDataFile does not return the node; look it up. */
  var node = FS.lookupPath(memfsPath).node;
  var blockSize = 512 * 1024;
  var cache = new Map();
  var maxBlocks = 32;

  function getBlock(idx) {
    if (cache.has(idx)) {
      var hit = cache.get(idx);
      cache.delete(idx);
      cache.set(idx, hit);
      return hit;
    }
    var start = idx * blockSize;
    var end = Math.min(totalBytes - 1, start + blockSize - 1);
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url, false);
    xhr.overrideMimeType("text/plain; charset=x-user-defined");
    xhr.setRequestHeader("Range", "bytes=" + start + "-" + end);
    xhr.send(null);
    if (xhr.status !== 200 && xhr.status !== 206) {
      throw new Error("range fetch failed: HTTP " + xhr.status + " " + url);
    }
    var txt = xhr.responseText || "";
    var bytes = new Uint8Array(txt.length);
    for (var i = 0; i < txt.length; i++) bytes[i] = txt.charCodeAt(i) & 0xff;
    if (cache.size >= maxBlocks) cache.delete(cache.keys().next().value);
    cache.set(idx, bytes);
    return bytes;
  }

  var origGetAttr = node.node_ops.getattr;
  node.node_ops = Object.assign({}, node.node_ops, {
    getattr: function (n) {
      var attr = origGetAttr(n);
      attr.size = totalBytes;
      return attr;
    },
  });

  node.stream_ops = Object.assign({}, node.stream_ops, {
    llseek: function (stream, offset, whence) {
      var pos = offset;
      if (whence === 1) pos += stream.position;
      else if (whence === 2) pos += totalBytes;
      if (pos < 0) throw new FS.ErrnoError(28);
      return pos;
    },
    read: function (stream, buffer, offset, length, position) {
      var pos = position !== undefined ? position : stream.position;
      if (pos >= totalBytes || length <= 0) return 0;
      var toRead = Math.min(length, totalBytes - pos);
      var readSoFar = 0;
      while (readSoFar < toRead) {
        var cur = pos + readSoFar;
        var blkIdx = Math.floor(cur / blockSize);
        var inBlk = cur % blockSize;
        var blk = getBlock(blkIdx);
        var take = Math.min(toRead - readSoFar, blk.length - inBlk);
        if (take <= 0) break;
        buffer.set(blk.subarray(inBlk, inBlk + take), offset + readSoFar);
        readSoFar += take;
      }
      if (position === undefined) stream.position += readSoFar;
      return readSoFar;
    },
  });
}
