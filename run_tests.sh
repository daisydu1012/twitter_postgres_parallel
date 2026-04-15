#!/bin/bash

failed=false

mkdir -p results

for problem in sql/*; do
    printf "%s " "$problem"
    problem_id=$(basename "${problem%.sql}")
    result="results/$problem_id.out"
    expected="expected/$problem_id.out"
    PGPASSWORD=pass psql -h localhost -p 5582 -U postgres -d postgres < "$problem" > "$result"
    DIFF=$(diff -B "$expected" "$result")
    if [ -z "$DIFF" ]; then
        echo pass
    else
        echo fail
        failed=true
    fi
done

if [ "$failed" = "true" ]; then
    exit 2
fi
