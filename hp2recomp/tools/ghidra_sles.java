import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.ArrayList;
import java.util.Comparator;

public class ghidra_sles extends GhidraScript {
    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        ArrayList<Function> fs = new ArrayList<>();
        FunctionIterator fi = fm.getFunctions(true);
        while (fi.hasNext()) fs.add(fi.next());
        println("=== SLES FUNCTION COUNT: " + fs.size() + " ===");
        fs.sort(Comparator.comparingLong((Function f) -> f.getBody().getNumAddresses()).reversed());
        println("=== TOP 25 BY SIZE ===");
        for (int i = 0; i < Math.min(25, fs.size()); i++) {
            Function f = fs.get(i);
            println("  " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses() + " " + f.getName());
        }
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        long[] want = {0x105130L};
        for (long a : want) {
            Function f = fm.getFunctionContaining(toAddr(a));
            if (f == null) { println("NO_FUNC entry " + Long.toHexString(a)); continue; }
            println("=== ENTRY FUNC " + f.getName() + " @ " + f.getEntryPoint() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 120, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) println(res.getDecompiledFunction().getC());
        }
    }
}
