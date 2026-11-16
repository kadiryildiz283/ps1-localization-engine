# Ghidra Jython post-script: bayrak ekranı fonksiyonunu bul.
# wait helper (0x60EC0) çağıranları + thunk hedeflerini decompile et.
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

fm = currentProgram.getFunctionManager()
rm = currentProgram.getReferenceManager()
decomp = DecompInterface()
decomp.openProgram(currentProgram)
monitor = ConsoleTaskMonitor()


def show(addr_int, label):
    addr = toAddr(addr_int)
    f = fm.getFunctionContaining(addr)
    if f is None:
        print("NO_FUNC %s @ %s" % (label, hex(addr_int)))
        return
    print("=== %s : %s @ %s ===" % (label, f.getName(), f.getEntryPoint()))
    res = decomp.decompileFunction(f, 90, monitor)
    if res and res.decompileCompleted():
        print(res.getDecompiledFunction().getC())
    else:
        print("decompile_fail")


for a, l in [(0x60EC0, "wait_helper"), (0x61024, "inner_wait"),
             (0x81820, "thunk_tgt_508"), (0x101418, "thunk_tgt_406")]:
    show(a, l)

print("=== XREFS to 0x60EC0 (wait helper cagiranlari) ===")
for ref in rm.getReferencesTo(toAddr(0x60EC0)):
    print("  from %s type=%s" % (ref.getFromAddress(), ref.getReferenceType()))

print("=== XREFS to 0x61024 ===")
for ref in rm.getReferencesTo(toAddr(0x61024)):
    print("  from %s type=%s" % (ref.getFromAddress(), ref.getReferenceType()))
