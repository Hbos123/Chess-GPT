#!/bin/bash
# Quick confidence test script - run before making changes to catch errors early

echo "🧪 Running Quick Confidence Tests..."
echo "=================================="
echo ""

echo "📊 Running confidence accuracy tests..."
cd backend
PYTHONPATH=. python3 -m pytest tests/test_confidence_accuracy.py -v --tb=short -x

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Confidence accuracy tests passed!"
    echo ""
    echo "📊 Running tree structure tests..."
    PYTHONPATH=. python3 -m pytest tests/test_tree_structure.py -v --tb=short -x
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ All quick tests passed!"
    else
        echo ""
        echo "❌ Tree structure tests failed"
        exit 1
    fi
else
    echo ""
    echo "❌ Confidence accuracy tests failed"
    exit 1
fi

