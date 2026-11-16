import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.TreeSet;

public class ghidra_flagui extends GhidraScript {
    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        ConsoleTaskMonitor mon = new ConsoleTaskMonitor();

        println("=== FUNCTION MAP 0x26000..0x42000 ===");
        TreeSet<Long> entries = new TreeSet<>();
        FunctionIterator fi = fm.getFunctions(true);
        while (fi.hasNext()) {
            Function f = fi.next();
            long e = f.getEntryPoint().getOffset();
            if (e >= 0x26000 && e < 0x42000) {
                entries.add(e);
                println(String.format("  %08x size=%d %s", e, f.getBody().getNumAddresses(), f.getName()));
            }
        }

        long[] targets = {0x3DD88L, 0x3B908L, 0x27C00L, 0x27820L};
        for (long t : targets) {
            Function f = fm.getFunctionContaining(toAddr(t));
            if (f == null) { println("NO_FUNC @ " + Long.toHexString(t)); continue; }
            println("=== FUNC " + f.getName() + " @ " + f.getEntryPoint()
                    + " size=" + f.getBody().getNumAddresses() + " (probe " + Long.toHexString(t) + ") ===");
            DecompileResults res = decomp.decompileFunction(f, 180, mon);
            if (res != null && res.decompileCompleted())
                println(res.getDecompiledFunction().getC());
            else
                println("decompile_fail");
        }
    }
}
