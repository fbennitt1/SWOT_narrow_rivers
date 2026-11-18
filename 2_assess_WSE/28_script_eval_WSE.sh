#!/bin/bash
#SBATCH --partition=cpu-preempt,ceewater_cjgleason-cpu
##SBATCH --exclude=ceewater-cpu[008-010]
#SBATCH --nodes=1 
##SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2 #1
#SBATCH --mem=24000
#SBATCH --time=20

#SBATCH --array=1996-2973%75  # 1-1995%50 # 99 # 1996-2973 

#SBATCH --output=../logs/log_2026_06_01_evalWSE_vD_rel_abs/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=eval_WSE

#setup env
module load conda/latest
conda activate narrowPIXC

#run code 
python3 -u 26_eval_WSE_rel_abs.py