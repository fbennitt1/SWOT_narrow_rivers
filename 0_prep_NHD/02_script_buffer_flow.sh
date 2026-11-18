#!/bin/bash
#SBATCH --partition=ceewater_cjgleason-cpu,cpu-preempt #gpu-preempt #gpu #cpu 
#SBATCH --nodes=1 
#SBATCH --ntasks-per-node=1 
#SBATCH --cpus-per-task=8
#SBATCH --mem=30000 #10000
#SBATCH --time=10 #4320 #2880 #in minutes

#SBATCH --array=0 #1-204 # %5 means limit the runs with 5 arrays at a time
#SBATCH --output=../logs/log_2025_09_23_buffer_flow_mean_extra/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=buffer_flowlines

#setup env
module load conda/latest
conda activate narrowPIXC

#run code
# arguments are the width_set from Bieger et al. 2015 (min, mean, or max) and
# extra which adds another 32 m to either side which is the diagonal of a 10 x 20 m
# SWOT pixel (extra, no)
python3 02_buffer_flowlines.py mean extra