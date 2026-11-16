import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.util.task.ConsoleTaskMonitor;
import java.util.HashSet;

public class ghidra_selref extends GhidraScript {
    @Override
    public void run() throws Exception {
        long sel = 0xD8B3CL;
        HashSet<String> funcs = new HashSet<>();
        println("=== XREFS to selection global 0x" + Long.toHexString(sel) + " ===");
        for (Reference ref : currentProgram.getReferenceManager().getReferencesTo(toAddr(sel))) {
            Address from = ref.getFromAddress();
            Function f = currentProgram.getFunctionManager().getFunctionContaining(from);
            String fn = (f != null) ? f.getEntryPoint().toString() : "no_func";
            println("  from " + from + " type=" + ref.getReferenceType() + " in " + fn);
            if (f != null) funcs.add(fn);
        }
        // also scan instructions for the address constant (lui/addiu pairs resolved by Ghidra)
        println("=== instruction operand scan for 0xD8B3C ===");
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            String s = ins.toString();
            if (s.contains("0xd8b3c") || s.contains("0xD8B3C")) {
                Function f = currentProgram.getFunctionManager().getFunctionContaining(ins.getAddress());
                String fn = (f != null) ? f.getEntryPoint().toString() : "no_func";
                println("  " + ins.getAddress() + " in " + fn + " : " + s);
                if (f != null) funcs.add(fn);
            }
        }
        println("=== referencing functions: " + funcs.size() + " ===");
        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        for (String fn : funcs) {
            Function f = currentProgram.getFunctionManager().getFunctionContaining(toAddr(fn));
            if (f == null) continue;
            println("=== FUNC " + f.getName() + " @ " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses() + " ===");
            DecompileResults res = decomp.decompileFunction(f, 120, new ConsoleTaskMonitor());
            if (res != null && res.decompileCompleted()) println(res.getDecompiledFunction().getC());
        }
    }
}
