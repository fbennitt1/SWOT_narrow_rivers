#!/bin/bash
#SBATCH --partition=ceewater_cjgleason-cpu,cpu-preempt
#SBATCH --nodes=1 
#SBATCH --ntasks-per-node=1 
#SBATCH --cpus-per-task=2 
#SBATCH --mem=64000
#SBATCH --time=1200 #700 for full 1000 #in minutes

#SBATCH --array=0-3 #1-48 #1-88 #0
#SBATCH --output=./logs/log_2026_03_28_filter_vD/log_%A_%a.log # job id: %A_ 
#SBATCH --job-name=extract_PIXC

#setup env
module load conda/latest
conda activate narrowPIXC

#run code
python3 14_extract_PIXC.py --version "D" --date "2026_03_28"
# python3 extract_PIXC.py --version "2_0" --date "2026_03_27"