#!/bin/bash
# Simple shell script that assist in the license calculation for
# Kubernetes Clusters. 
#

# ----------------------
# Variables declaration and helper 
# functions

NAMESPACES_TO_EXCLUDE="system|dynatrace|cert-manager|istio"
namespaces_msg="
 The following namespaces will be exluded from the Gib/h calculation.
 Modify the 'NAMESPACES_TO_EXCLUDE' variable so the estimation suits your 
 cluster accordingly. Add words to the exclusion list and separate each 
 with a pipe '|'. The exclusion is case insensitive.
 
 NAMESPACES_TO_EXCLUDE=$NAMESPACES_TO_EXCLUDE
 "

# --- Variables --

# List prices $0.002 per POD-hour in USD
price_pod_hour=0.002
# List price  $0.01 per GiB-hour AppOnly in USD
price_gib_hour=0.01

declare -r min_memory=256
declare -a rounded_memories
declare -a actual_memories
declare -i total_pods

# -- functions -- 
timestamp() {
    date +"[%Y-%m-%d %H:%M:%S]"
}

printInfo() {
    echo ""
    echo "     $1"
}

printInfoSection() {
    echo ""
    echo "$thickline"
    echo "$halfline $1 $halfline"
    echo "$thinline"
}

thickline="======================================================================"
halfline="============"
thinline="______________________________________________________________________"
infolog="[License-estimation|INFO] $(timestamp) |"


#
# ---- License estimation logic
#
getClusterInfo() {
    printInfoSection "Cluster Information"
    printInfo Cluster-Info
    kubectl cluster-info

    printInfo "Nodes Utilization"
    kubectl top nodes
}

calculatePodHours() {

    # Calculation of the POD Hours for the Year
    printInfoSection "POD Hours Calculation"

    total_pods=$(kubectl get pods --all-namespaces --no-headers | wc -l)
    # Command 1: This will help to estimate the average # of pods running per day
    printInfo "SUM of PODs in the Cluster: $total_pods"

    printInfo "Assuming these $total_pods pods run for 24 hours"
    printInfo "The daily pod-hour consumption is $((total_pods * 24)) pod-hours"
    
}

calculateMemoryRoundUp() {
    printInfoSection "POD Memory Calculation"
    i=0

    echo "$namespaces_msg"
    # Snapshot of actual PODs with their Utilization
    pods_top=$(kubectl top pods --all-namespaces --no-headers | grep -viE $NAMESPACES_TO_EXCLUDE )
    
    echo "Calculating and rounding up memory of the pods"
    # See comments in 'done' to understand the process substitution
    while read -r line; 
    do
        # We extract the Memory in Mi
        mem_s=$(echo "$line" | awk '{print($4)}')
        # We extract only the integer
        m=$(echo "$mem_s" | tr -dc '0-9')
        if ((m < min_memory)); then
            m_rounded=$min_memory
        else
            # Calculate the dividend
            dividend=$((m / min_memory))

            m_rounded=$((dividend * min_memory))

            # If we have remainders we increase to next round up
            if [[ $((m % min_memory)) -gt 0 ]]; then
                m_rounded=$((m_rounded + min_memory))
            fi
        fi

        # Save value to array
        rounded_memories[i]=$m_rounded
        actual_memories[i]=$m
        # TODO: better would be to create summary of #PODs and its Memory per NS.
        # We round up to 256
        echo "$i|$line rounded to $m_rounded Mi"
        ((i++))

    # We read the output using process substitution to save the results in an array within the same process 
    # otherwise the array endsup empty after the while loop
    # Using "Quotes" for preserving Multilines
    done < <(echo "${pods_top}")

    echo "------------"
    echo "Finished rounding up"
    echo ""
}

calculateMemoryDailyUsage(){
     
    printInfoSection "POD Memory usage Estimation"
    
    for k in "${!rounded_memories[@]}"
    do
        total_memory_rounded=$((total_memory_rounded + rounded_memories[k]))
        total_memory_actual=$((total_memory_actual + actual_memories[k]))
    done
    total_memory_rounded=$((total_memory_rounded * 24 ))
    total_memory_actual=$((total_memory_actual * 24 ))

    printInfo "For the ${#rounded_memories[@]} PODs these are the calculations assuming they run 24/7 for 30 days"

    echo "Daily Total Memory rounded $total_memory_rounded Mi/h"
    echo "Daily Total Memory actual $total_memory_actual Mi/h"
    echo ""
    echo "Monthly (30 days) Total Memory rounded $(( (total_memory_rounded  * 30 ) / 1024 )) GiB-hours"
    echo "Monthly (30 days) Total Memory actual $(( (total_memory_actual  * 30 ) / 1024 )) GiB-hours"
    echo ""
    echo "Yearly (365 days) Total Memory rounded $(( (total_memory_rounded  * 365 ) / 1024 )) GiB-hours"
    echo "Yearly (365 days) Total Memory actual $(( (total_memory_actual  * 365 ) / 1024 )) GiB-hours"
}

calculateEstimation(){

     printInfoSection "POD-Hour and GiB-Hour Monthly and Yearly costs estimation"

     echo ""
     echo "---- POD-hour estimation ---- "
     echo "The price for POD-hour is $ $price_pod_hour USD"
     pod_hours_month=$((total_pods * 24 * 30))
     # Using AWK for floating number calculation 
     pod_hours_month_est=$(echo $pod_hours_month $price_pod_hour | awk '{print $1 * $2}' )
     echo "The price for $pod_hours_month monthly pod-hours is: $ $pod_hours_month_est USD"
     echo ""
     
     
     echo ""
     echo "---- GiB-hour estimation ---- "
     echo "The price for GiB-hour is $ $price_gib_hour USD"
     gib_hour_month=$(( (total_memory_rounded * 30 ) / 1024 ))
     gib_hour_year=$(( (total_memory_rounded * 365 ) / 1024 ))
    
     # Using AWK for floating number calculation 
     gib_hour_month_est=$(echo $gib_hour_month $price_gib_hour | awk '{print $1 * $2}' )
     gib_hour_year_est=$(echo $gib_hour_year $price_gib_hour | awk '{print $1 * $2}' )
     echo "The price for $gib_hour_month monthly GiB-hours is: $ $gib_hour_month_est USD"
     echo "The price for $gib_hour_year yearly GiB-hours is: $ $gib_hour_year_est USD"
     echo ""

}




getClusterInfo

calculatePodHours

calculateMemoryRoundUp

calculateMemoryDailyUsage

calculateEstimation

