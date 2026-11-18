#!/bin/bash
#SBATCH --partition=cpu-preempt,ceewater_cjgleason-cpu #gpu-preempt #gpu #cpu
#SBATCH --nodes=1 
##SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4 #8
#SBATCH --mem=15000 #50000
#SBATCH --time=7 #30 #in minutes 

#SBATCH --array=1138,2243,6654,7314

#SBATCH --output=../logs/log_2025_12_07_HUC2_03_vD_denom_fix/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=evalPIXC

#setup env
module load conda/latest
conda activate narrowPIXC

#run code 
python3 16_eval_denom_vD.py mean # CHANGE