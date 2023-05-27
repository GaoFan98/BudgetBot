#!/bin/bash

function run {
    python main.py
}

export -f run
watchmedo auto-restart --recursive --pattern="*.py" --ignore-directories --signal=SIGTERM -- bash -c run
