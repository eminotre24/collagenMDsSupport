# Libraries
import os
import datetime
import shutil

# ------------ Generate Setup Files (Preparation pre-ACENET) ------------

def generate_files_prep(name, pdb_file, ff, watertype, solvent_config, pion, nion, emtol, dimensions = None, angles = None, distance = None, ccon = None, chain_org = True):
    # Generate preparation files, the structure of the folder of the "project" and the steps scripts ready to jsut execute
    val_sep = 15
    # Folders
    date_today = datetime.datetime.today().strftime('-%d%m')
    name_folder = name + date_today
    files_folder = name_folder + "/" + name + "-files"
    os.makedirs(name_folder, exist_ok=True)
    os.makedirs(files_folder, exist_ok=True)

    # Files
    if os.path.isdir("templates/" + ff + ".ff"):
        shutil.copytree("templates/" + ff + ".ff", files_folder + "/" + ff + ".ff")
    shutil.copy("templates/tempem.mdp", files_folder + "/ions.mdp")
    # Add emtol
    with open(files_folder + "/ions.mdp", "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Title
        if stripped.startswith("emtol"):
            lines[i] = f"{'emtol':<{val_sep}} = {emtol}\n"

    shutil.copy(files_folder + "/ions.mdp", files_folder + "/minimize.mdp")
    # Change Longrange Int.
    with open(files_folder + "/minimize.mdp", "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Title
        if stripped.startswith("coulombtype"):
            lines[i] = f"{'coulombtype ':<{val_sep}} = PME\n"
    with open(files_folder + "/minimize.mdp", "w") as f:
        f.writelines(lines)

    shutil.copy(pdb_file, files_folder)

    with open(files_folder + "/steps.sh", "w") as file:
        # Generate script
        file.write(f"gmx pdb2gmx -f {os.path.basename(pdb_file)} -o colfib.gro -ff {ff} -water {watertype}\n")

        if chain_org:
            file.write("mkdir itp_chains\n")
            file.write("mv *.itp ./itp_chains/\n")
            file.write(r"""sed -i '' -E '/^;[[:space:]]*Include chain topologies[[:space:]]*$/, /^;[[:space:]]*Include water topology[[:space:]]*$/ s@^([[:space:]]*#include ")@\1itp_chains/@' topol.top""")
            file.write("\n")
        
        if distance is None:
            file.write(f"gmx editconf -f colfib.gro -o colfib-boxd.gro -c -box {dimensions} -angles {angles}\n")
        else:
            file.write(f"gmx editconf -f colfib.gro -o colfib-boxd.gro -c -d {distance}\n")

        file.write(f"gmx solvate -cp colfib-boxd.gro -cs {solvent_config} -o colfib-solvtd.gro -p topol.top\n")
        file.write("gmx grompp -f ions.mdp -c colfib-solvtd.gro -p topol.top -o ions.tpr\n")

        if ccon is None:
            file.write(f"echo 13 | gmx genion -s ions.tpr -o colfib-solvion.gro -p topol.top -pname {pion} -nname {nion} -neutral\n")
        else:
            file.write(f"echo 13 | gmx genion -s ions.tpr -o colfib-solvion.gro -p topol.top -pname {pion} -nname {nion} -neutral -conc {ccon}\n")

    

    print("Files generated in folder: " + name_folder)

# ------------ ACENET Script Generation ------------

def generate_script(name, runtime, user, steps):
    # Generate ACENET script
    date_today = datetime.datetime.today().strftime('-%d%m')
    name_dated = name + date_today
    name_folder = name + "-files"
    script_path = f"{name_dated}/{name}-script.sh"
    
    with open(script_path, "w") as file:
        # Generate script
        file.write(f"#!/bin/bash\n")
        # Naming
        file.write(f"#SBATCH --job-name={name_dated}\n")
        file.write(f"#SBATCH --output=/home/aenovt/out_err/{name_dated}/slurm-%j.out\n")
        file.write(f"#SBATCH --error=/home/aenovt/out_err/{name_dated}/slurm-%j.err\n")
        # Runtime
        file.write(f"#SBATCH --time={runtime}\n")
        # Specs
        file.write(f"#SBATCH --nodes=1\n")
        file.write(f"#SBATCH --ntasks=1\n")
        file.write(f"#SBATCH --cpus-per-task=12\n")
        file.write(f"#SBATCH --gres=gpu:1\n")
        file.write(f"#SBATCH --mem-per-cpu=2G\n")
        # Notifications
        file.write(f"#SBATCH --mail-type=BEGIN,END,FAIL\n")
        file.write(f"#SBATCH --mail-user={user}\n")
        file.write("\n")
        # Startup
        file.write("module purge\n")
        file.write("module load StdEnv/2023 gcc/12.3 openmpi/4.1.5 cuda/12.2 gromacs/2024.4\n")
        file.write(f"cd /home/aenovt/scratch/{name_folder}\n")
        file.write('export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"\n')
        file.write("\n")
        # Processes
        if steps[0]: # EM
            file.write("srun gmx grompp -f minimize.mdp -c colfib-solvion.gro -p topol.top -o em.tpr\n")
            file.write("srun gmx mdrun -deffnm em -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu\n")
            file.write("\n")

        if steps[1]: # NVT
            file.write("srun gmx grompp -f nvt_heating.mdp -c em.gro -r em.gro -p topol.top -o nvt_heating.tpr\n")
            file.write("srun gmx mdrun -deffnm nvt_heating -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu\n")
            file.write("srun gmx grompp -f nvt_equilibration.mdp -c nvt_heating.gro -r nvt_heating.gro -t nvt_heating.cpt -p topol.top -o nvt_equilibration.tpr\n")
            file.write("srun gmx mdrun -deffnm nvt_equilibration -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu\n")
            file.write("\n")

        if steps[2]: # NPT
            file.write("srun gmx grompp -f npt.mdp -c nvt_equilibration.gro -r nvt_equilibration.gro -t nvt_equilibration.cpt -p topol.top -o npt.tpr\n")
            file.write("srun gmx mdrun -deffnm npt -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu\n")
            file.write("\n")

        if steps[3]: # MD Run
            file.write("srun gmx grompp -f md.mdp -c npt.gro -t npt.cpt -p topol.top -o md_1.tpr -maxwarn 2\n")
            file.write("srun gmx mdrun -deffnm md_1 -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu\n")
            file.write("\n")

    print("SLURM script generated with name: " + script_path)

# ------------ MDP Files Generation Function ------------

def mdp_parms(name, cutoff, temperature , pressure, taup, nvt_time, npt_time, md_time, dt_eq, dt_md):
    val_sep = 23
    date_today = datetime.datetime.today().strftime('-%d%m')
    name_folder = name + date_today
    files_folder = name_folder + "/" + name + "-files"

    nsteps_nvt = int(nvt_time/2 * 1e6 / dt_eq) # fs * nsteps = ns/2
    nsteps_npt = int(npt_time * 1e6 / dt_eq) # same but the npt is just 1 process
    nsteps_md = int(md_time * 1e6 / dt_md)

    write_nvts(files_folder, cutoff, temperature, nsteps_nvt, nvt_time, dt_eq, val_sep)
    write_npt(files_folder, nsteps_npt, npt_time, dt_eq, taup, pressure, val_sep)
    write_md(files_folder, nsteps_md, md_time, dt_md, val_sep)
    
    # Write scripts
    print("MDP files generated")

# --- WRITING FUNCTIONS ---

def write_nvts(folder, cutoff, temperature, nsteps_nvt, nvt_time, dt_eq, val_sep):
    # NVT Heating
    shutil.copy("templates/tempmdp.mdp", folder + "/nvt_heating.mdp")
    with open(folder + "/nvt_heating.mdp", "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Title
        if stripped.startswith("title"):
            lines[i] = f"{'title':<{val_sep}} = NVT Heating\n"
        # Time
        elif stripped.startswith("nsteps"):
            lines[i] = f"{'nsteps':<{val_sep}} = {nsteps_nvt:<9} ; {nvt_time/2} ns\n"
            lines[i+1] = f"{'dt':<{val_sep}} = {dt_eq/1e3}\n"
        # Cutoffs
        elif stripped.strip().startswith("rcoulomb"):
            lines[i] = f"{'rcoulomb':<{val_sep}} = {cutoff}\n"
        elif stripped.strip().startswith("rvdw"):
            lines[i] = f"{'rvdw':<{val_sep}} = {cutoff}\n"
        # Temperature
        elif stripped.startswith("ref_t"):
            lines[i] = f"{'ref_t':<{val_sep}} = {temperature:<7} {temperature:<7}\n"
        elif stripped.startswith("gen_temp"):
            lines[i] = f"{'gen_temp':<{val_sep}} = {temperature}\n"
    with open(folder + "/nvt_heating.mdp", "w") as f:
        f.writelines(lines)
    
    # NVT Equilibration
    shutil.copy(folder + "/nvt_heating.mdp", folder + "/nvt_equilibration.mdp")
    with open(folder + "/nvt_equilibration.mdp", "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Title
        if stripped.startswith("title"):
            lines[i] = f"{'title':<{val_sep}} = NVT Equilibration\n"
        # A continuation
        if stripped.startswith("continuation"):
            lines[i] = f"{'continuation':<{val_sep}} = yes\n"
        # No GenVel
        elif stripped.startswith("gen_vel"):
            lines[i] = f"{'gen_vel':<{val_sep}} = no\n"
            del lines[i+1:i+3]
    with open(folder + "/nvt_equilibration.mdp", "w") as f:
        f.writelines(lines)
    
def write_npt(folder, nsteps_npt, npt_time, dt_eq, tau_p, pressure, val_sep):
    shutil.copy(folder + "/nvt_equilibration.mdp", folder + "/npt.mdp")
    with open(folder + "/npt.mdp", "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Title
        if stripped.startswith("title"):
            lines[i] = f"{'title':<{val_sep}} = NPT\n"
        
        # Time
        elif stripped.startswith("nsteps"):
            lines[i] = f"{'nsteps':<{val_sep}} = {nsteps_npt:<9} ; {npt_time} ns\n"
            lines[i+1] = f"{'dt':<{val_sep}} = {dt_eq/1e3}\n"

        # Cutoffs - Same as Heating
        # Temperature - Same as Heating

        # Pressure Coupling
        elif stripped.startswith("pcoupl"):
            pressure_block = [
                f"{'pcoupl':<{val_sep}} = C-rescale\n",
                f"{'pcoupltype':<{val_sep}} = isotropic\n",
                f"{'tau_p':<{val_sep}} = {tau_p}\n",
                f"{'ref_p':<{val_sep}} = {pressure}\n",
                f"{'compressibility':<{val_sep}} = 4.5e-5\n",
                f"{'refcoord_scaling':<{val_sep}} = com\n"
            ]
            lines[i:i+1] = pressure_block
            break

    with open(folder + "/npt.mdp", "w") as f:
        f.writelines(lines)

def write_md(folder, nsteps_md, md_time, dt_md, val_sep):
    nstxout_set = False
    shutil.copy(folder + "/npt.mdp", folder + "/md.mdp")
    with open(folder + "/md.mdp", "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Title
        if stripped.startswith("title"):
            lines[i] = f"{'title':<{val_sep}} = MD Run\n"
        # Remove position restrain
        elif stripped.startswith("define"):
            del lines[i]
        # Time
        elif stripped.startswith("nsteps"):
            lines[i] = f"{'nsteps':<{val_sep}} = {nsteps_md:<9} ; {md_time} ns\n"
            lines[i+1] = f"{'dt':<{val_sep}} = {dt_md/1e3}\n"
            # Insert COM Restrains
            lines.insert(i + 2, f"{'comm-mode':<{val_sep}} = Angular\n")
            lines.insert(i + 3, f"{'comm-grps':<{val_sep}} = Protein\n")
        # Out Kinematics
        elif stripped.startswith("nstxout") and (nstxout_set == False):
            lines[i] = f"{'nstxout':<{val_sep}} = 0\n"
            lines[i + 1] = f"{'nstvout':<{val_sep}} = 0\n"
            lines.insert(i + 2, f"{'nstfout':<{val_sep}} = 0\n")
            nstxout_set = True
        # Output Macros
        elif stripped.startswith("nstenergy"):
            lines[i + 1] = f"{'nstlog':<{val_sep}} = 50000\n"
            lines.insert(i + 2, f"{'nstxout-compressed':<{val_sep}} = 50000\n")
            lines.insert(i + 3, f"{'compressed-x-grps':<{val_sep}} = System\n")

    with open(folder + "/md.mdp", "w") as f:
        f.writelines(lines)