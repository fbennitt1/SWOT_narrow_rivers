#!/bin/bash
#SBATCH --partition=cpu-preempt # ceewater_cjgleason-cpu #gpu-preempt #gpu #cpu 
#SBATCH --nodes=1 
#SBATCH --ntasks-per-node=1 
#SBATCH --cpus-per-task=8
#SBATCH --mem=50000 # several hucs failed on 30000
#SBATCH --time=45 #4320 #2880 #in minutes

#SBATCH --array=41#0-204 # %5 means limit the runs with 5 arrays at a time
#SBATCH --output=../logs/log_2025_09_23_buffer_seg_mean/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=buffer_segments

#setup env
module load conda/latest
conda activate narrowPIXC

#run code
python3 02a_buffer_segments.py mean