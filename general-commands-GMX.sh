# GENERAL STEPS FOR GROMACS

# Generate GROMACS Files
gmx pdb2gmx -f ticf.pdb -o ticf_p.gro -water tip3p -ff amber14sb

# Save itp files in itp chains and update topol - In case there are too much files - Clean Purposes
mkdir itp_chains
mv *.itp ./itp_chains/
# update the direction in the topology file - given the format
sed -i '' '/^; Include chain topologies$/,/^; Include water topology$/ {
  s#^\(\#include "\)\(.*\.itp\)"#\1itp_chains/\2#
}' topol.top

# Improved itp saving
mkdir itp_chains
mv *.itp ./itp_chains/
sed -i '' -E '/^;[[:space:]]*Include chain topologies[[:space:]]*$/, /^;[[:space:]]*Include water topology[[:space:]]*$/ s@^([[:space:]]*#include ")@\1itp_chains/@' topol.top

# Set Up the System Dimensions and Configuration
gmx editconf -f ticf_p.gro -o ticf_boxd.gro -c -box 16.0 16.0 72.0 -angles 90.0 90.0 90.0

# Solvate the System
gmx solvate -cp ticf_boxd.gro -cs spc216.gro -o ticf_solvtd.gro -p topol.top

# Prepare the Ionization
gmx grompp -f ions.mdp -c ticf_solvtd.gro -p topol.top -o ions.tpr

# Ionize the System
gmx genion -s ions.tpr -o ticf_solvtd_ions.gro -p topol.top -pname NA -nname CL -neutral
13

# Suggestion - Generate the em.tpr, and send it, the itp files, the force field, and the top file

# Prepare the minimization process
gmx grompp -f minimize.mdp -c ticf_solvtd_ions.gro -p topol.top -o em.tpr

# Run the minimization process
gmx mdrun -deffnm em

# Post Analysis
gmx energy -f em.edr -o datafiles/potential.xvg

# Same process for NVT - First "Actual" MD
gmx grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr
gmx mdrun -deffnm nvt

# Same but for NPT - ITS A CONTINUATION
gmx grompp -f npt.mdp -c nvt.gro -r nvt.gro -t nvt.cpt -p topol.top -o npt.tpr
gmx mdrun -deffnm npt

# Production Phase
gmx grompp -f md.mdp -c npt.gro -t npt.cpt -p topol.top -o md_0_1.tpr
gmx mdrun -deffnm md_0_1

# Continue Production Phase
srun gmx mdrun -s md_1.tpr -cpi md_1.cpt -deffnm md_1 -append -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu

# Boundary Conditions Unwrapping - After Finishing Production Phase - Center Protein, Output System
gmx trjconv -s md_0_1.tpr -f md_0_1.xtc -o md_0_1_noPBC.xtc -pbc mol -center

# No center given no momenta of COM
gmx trjconv -s md_0_1.tpr -f md_0_1.xtc -o md_0_1_noPBC.xtc -pbc mol

# Get COM evolution
gmx traj -f md_1.xtc -s md_1.tpr -ox com.xvg -com

# Extension of a finished sim - extension is in ps, regardless of the steps.
gmx convert-tpr -s md_1.tpr -extend 50000000 -o md_1_cont.tpr
gmx mdrun -s md_1_cont.tpr -cpi md_1.cpt -deffnm md_1 -append -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu
