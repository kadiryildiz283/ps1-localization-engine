import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.scalar.Scalar;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.HashSet;

public class ghidra_search extends GhidraScript {
    @Override
    public void run() throws Exception {
        long[] targets = {0xA800L, 0xA7F0L, 0x20943L, 0x1323L};
        HashSet<String> funcs = new HashSet<>();
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            for (int op = 0; op < ins.getNumOperands(); op++) {
                Object[] objs = ins.getOpObjects(op);
                for (Object o : objs) {
                    if (o instanceof Scalar) {
                        long v = ((Scalar) o).getUnsignedValue();
                        for (long t : targets) {
                            if (v == t) {
                                Address a = ins.getAddress();
                                Function f = currentProgram.getFunctionManager().getFunctionContaining(a);
                                String fn = (f != null) ? f.getEntryPoint().toString() : "no_func";
                                println("CONST 0x" + Long.toHexString(t) + " at " + a + " in " + fn + " : " + ins);
                                if (f != null) funcs.add(fn);
                            }
                        }
                    }
                }
            }
        }
        println("=== FUNCTIONS with target constants: " + funcs.size() + " ===");
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        int n = 0;
        for (String fn : funcs) {
            if (n++ >= 8) break;
            Function f = currentProgram.getFunctionManager().getFunctionContaining(toAddr(fn));
            if (f == null) continue;
            println("=== FUNC " + f.getName() + " @ " + f.getEntryPoint() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 90, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) println(res.getDecompiledFunction().getC());
        }
    }
}
