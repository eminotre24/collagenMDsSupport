# --- SCRIPT ---
# Initialize
gmx pdb2gmx -f colfib-2db.pdb -o colfib.gro -ff amber99sb-star-ildnp -water tip3p

# Chains storage - when we have 2 many fragments
mkdir itp_chains
mv *.itp ./itp_chains/
sed -i '' -E '/^;[[:space:]]*Include chain topologies[[:space:]]*$/, /^;[[:space:]]*Include water topology[[:space:]]*$/ s@^([[:space:]]*#include ")@\1itp_chains/@' topol.top

# Set Box Dimensions
gmx editconf -f colfib.gro -o colfib-boxd.gro -c -box 19.0 19.0 140.0 -angles 90.0 90.0 90.0

# Add water molecules
gmx solvate -cp colfib-boxd.gro -cs spc216.gro -o colfib-solvtd.gro -p topol.top

# Ionize
gmx grompp -f ions.mdp -c colfib-solvtd.gro -p topol.top -o ions.tpr
gmx genion -s ions.tpr -o colfib-solvion.gro -p topol.top -pname NA -nname CL -neutral
# 13

# Pass to ACENET





