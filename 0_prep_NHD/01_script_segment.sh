#!/bin/bash
#SBATCH --partition=cpu-preempt # ceewater_cjgleason-cpu
#SBATCH --nodes=1 
#SBATCH --ntasks-per-node=1 
#SBATCH --cpus-per-task=8
#SBATCH --mem=20000 #64512
#SBATCH --time=10 #4320

#SBATCH --array=41# 0-196,198-204 # %5 means limit the runs with 5 arrays at a time
#SBATCH --output=../logs/log_2025_09_23_segment/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=segment_NHD

#setup env
module load conda/latest
conda activate narrowPIXC

#run code
python3 01_segment_NHD.py