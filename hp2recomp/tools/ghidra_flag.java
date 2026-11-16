import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.util.task.ConsoleTaskMonitor;

public class ghidra_flag extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        long[] addrs = {0x60EC0L, 0x61024L, 0x81820L, 0x101418L};
        String[] labels = {"wait_helper", "inner_wait", "thunk_tgt_508", "thunk_tgt_406"};
        for (int i = 0; i < addrs.length; i++) {
            Address a = toAddr(addrs[i]);
            Function f = currentProgram.getFunctionManager().getFunctionContaining(a);
            if (f == null) { println("NO_FUNC " + labels[i] + " @ " + Long.toHexString(addrs[i])); continue; }
            println("=== " + labels[i] + " : " + f.getName() + " @ " + f.getEntryPoint() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 90, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) println(res.getDecompiledFunction().getC());
            else println("decompile_fail");
        }
        println("=== XREFS to 0x60EC0 ===");
        for (Reference ref : currentProgram.getReferenceManager().getReferencesTo(toAddr(0x60EC0L)))
            println("  from " + ref.getFromAddress() + " type=" + ref.getReferenceType());
        println("=== XREFS to 0x61024 ===");
        for (Reference ref : currentProgram.getReferenceManager().getReferencesTo(toAddr(0x61024L)))
            println("  from " + ref.getFromAddress() + " type=" + ref.getReferenceType());
    }
}
