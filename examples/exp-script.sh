#!/bin/bash
#SBATCH --job-name=example-script
#SBATCH --output=/home/aenovt/out_err/example-script/slurm-%j.out
#SBATCH --error=/home/aenovt/out_err/example-script/slurm-%j.err
#SBATCH --time=7-00:00:00            # Max Time
#SBATCH --nodes=1					  # Resources based on Benchmark ID=205
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12			  #	OPENMP
#SBATCH --gres=gpu:1				  # GPU
#SBATCH --mem-per-cpu=2G              # RAM
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=a00836485@tec.mx

# Load GROMACS (In parallel for optimization of the system)
module purge
module load StdEnv/2023 gcc/12.3 openmpi/4.1.5 cuda/12.2 gromacs/2024.4          # Load gromacs and other

# Get the threads from the variable cpus per task - should be same number
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"

# Move to output dir to save files there
cd /home/aenovt/scratch/example-files

# Energy Minimization Phase
srun gmx grompp -f minimize.mdp -c cfdp-solvion.gro -p topol.top -o em.tpr
srun gmx mdrun -deffnm em -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu

# Heating Phase
srun gmx grompp -f nvt_heating.mdp -c em.gro -r em.gro -p topol.top -o nvt_heating.tpr
srun gmx mdrun -deffnm nvt_heating -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu

# Prepare and Run NVT - Equilibration Phase
srun gmx grompp -f nvt_equilibration.mdp -c nvt_heating.gro -r nvt_heating.gro -t nvt_heating.cpt -p topol.top -o nvt_equilibration.tpr
srun gmx mdrun -deffnm nvt_equilibration -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu

# Prepare and Run NPT Phase
srun gmx grompp -f npt.mdp -c nvt_equilibration.gro -r nvt_equilibration.gro -t nvt_equilibration.cpt -p topol.top -o npt.tpr
srun gmx mdrun -deffnm npt -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu

# Run Production Phase - Max Warn as we are restraining COM linear and angular momenta
srun gmx grompp -f md.mdp -c npt.gro -t npt.cpt -p topol.top -o md_1.tpr -maxwarn 2
srun gmx mdrun -deffnm md_1 -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu