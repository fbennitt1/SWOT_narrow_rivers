#!/bin/bash
#SBATCH --partition=ceewater_cjgleason-cpu,cpu-preempt
#SBATCH --nodes=1 
#SBATCH --ntasks-per-node=1 
#SBATCH --cpus-per-task=2 
#SBATCH --mem=30000 #30000 #64512  #
#SBATCH --time=60 #4320 #2880 #in minutes

#SBATCH --array=180-204 #108 #1-204 # 51-57,108-112 # %5 means limit the runs with 5 arrays at a time
#SBATCH --output=../logs/log_2025_09_23_prep/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=prep_NHD

#setup env
module load conda/latest
conda activate narrowPIXC

#run code
python3 00_prep_NHD.py
#If version with waterbodies included is desired, use this:
# python3 00_prep_NHD_keep_waterbody.py