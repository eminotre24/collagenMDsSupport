# collagenMDsSupport

The notebook [script generator](./files-gen-wf.ipynb) implements the module [colfib](./colfib.py), which contains functions that based on templates of my own scripts, to generate new scripts with different parameters for running a simulation. The use of this notebook is pretty simple, with most specifications in both the notebook and in the functions contained in the module. The structure for running the commands is:
 -`steps.sh` is ran locally, using `chmod +x` to activate it, and previously having activated the `GMX` executable through `source /usr/local/gromacs/bin/gmxrc`, which should have the path to the executable. The version used is the **2024.4**, in accordance to the latest version at the time implemented in ACENET.
 -`{filename}-script.sh` is the script to run remotely, using the command `sbatch {filename}-script.sh`. Consider also the resources asked for, as the limit may ary across different clusters.

 ## General GMX commands

 ### Simulation Settings

Command used to generate gromacs files necesary to start a simulation, using the `.pdb` file, and the force field selected (should be in the folder if its not one of the implemented in gromacs).
```
gmx pdb2gmx -f ticf.pdb -o ticf_p.gro -water tip3p -ff amber14sb
```

---

**Optional**: Save itp files generated (related with topology) in a single folder `itp_chains`, and also edit the `.top` file to search for this files. Cleanes
```
mkdir itp_chains
mv *.itp ./itp_chains/
sed -i '' -E '/^;[[:space:]]*Include chain topologies[[:space:]]*$/, /^;[[:space:]]*Include water topology[[:space:]]*$/ s@^([[:space:]]*#include ")@\1itp_chains/@' topol.top
```

---

Set up dimensions and configuration of the container of the simulation. It can be done either defining spacing between protein and borders, or a custom box's dimentions.
```
gmx editconf -f ticf_p.gro -o ticf_boxd.gro -c -box 16.0 16.0 72.0 -angles 90.0 90.0 90.0
```
or 
```
gmx editconf -f ticf_p.gro -o ticf_boxd.gro -c -d 3.0 -bt cubic
```

---

Solvate the system: Add the solvate configuration (water), and the type of geometry - in this case spc216, explicit.

```
gmx solvate -cp ticf_boxd.gro -cs spc216.gro -o ticf_solvtd.gro -p topol.top
```

---

Prepare the ionization (its like an "md", but it really isnt), to input the appropiate ions/anions. The `ions.mdp` should have similar parameters to `em.mdp`.
```
gmx grompp -f ions.mdp -c ticf_solvtd.gro -p topol.top -o ions.tpr
```

---

Make the "md" (make gromacs input the ions), and the option `13` should be selected to input this ions replacing solvent molecules only, not protein ones. Here we selected the respective atoms for both positive chargge (Na) and negative (Cl)
```
gmx genion -s ions.tpr -o ticf_solvtd_ions.gro -p topol.top -pname NA -nname CL -neutral
```

---
#### I would recommend, specialy in large simulations, to do the following steps in the cluster

Prepare the minimization "md". This is not an "md" as such, the system tries to reach a more stable energy configuration changing the arrangment of the molecules. This is with the purpose of not having artificial forces given to random placement of solvent.
```
gmx grompp -f minimize.mdp -c ticf_solvtd_ions.gro -p topol.top -o em.tpr
```

Then, we can run the minimization process, simply by doing
```
gmx mdrun -deffnm em
```

---

Additionally to this, you can then make other types of equilibrations, both for temperature and pressure of the system, in order to have a semi stable structure at the start of your actual simulation.

```
gmx grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr
gmx mdrun -deffnm nvt

gmx grompp -f npt.mdp -c nvt.gro -r nvt.gro -t nvt.cpt -p topol.top -o npt.tpr
gmx mdrun -deffnm npt

gmx grompp -f md.mdp -c npt.gro -t npt.cpt -p topol.top -o md_0_1.tpr
gmx mdrun -deffnm md_0_1
```

For parallelization purposes you can add to the command `gmx mdrun` the following (I use this in the clusters, for example)
```
gmx mdrun -deffnm md_0_1 -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu
```

### Analysis

For obtaining **state variables** and other trackable variables, you can use the following command and choose. The filename doesnt define the option, and should have the extension `.xvg`.
```
gmx energy -f em.edr -o datafiles/potential.xvg
```

---

Unwrap trajectories of atoms and generate a new file with the trajectories unwrapped. Parameters such as boundary conditions and centering of the atoms can be choosen.
```
gmx trjconv -s md_0_1.tpr -f md_0_1.xtc -o md_0_1_noPBC.xtc -pbc mol -center
```

---

Get the Center of Momenta of the protein.
```
gmx traj -f md_1.xtc -s md_1.tpr -ox com.xvg -com
```

 ### Extras

Continue a simulation that timed out
```
srun gmx mdrun -s md_1.tpr -cpi md_1.cpt -deffnm md_1 -append -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu
```

---

Extend a simulation. Extension in $\text{ps}$, regardless of steps parameters.*
```
gmx convert-tpr -s md_1.tpr -extend 50000000 -o md_1_cont.tpr
gmx mdrun -s md_1_cont.tpr -cpi md_1.cpt -deffnm md_1 -append -ntomp $OMP_NUM_THREADS -ntmpi $SLURM_NTASKS -nb gpu -pme gpu -update gpu -bonded cpu
```