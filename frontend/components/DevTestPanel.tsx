/**
 * Developer Test Panel
 * 
 * In-UI testing panel for quick feature verification during development.
 * Provides one-click tests for common scenarios.
 */

'use client';

import { useState } from 'react';
import { getBackendBase } from '@/lib/backendBase';

interface TestResult {
  name: string;
  status: 'running' | 'passed' | 'failed';
  message?: string;
  duration?: number;
}

export default function DevTestPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [results, setResults] = useState<TestResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const tests = [
    {
      name: 'Engine Health',
      run: async () => {
        const response = await fetch(`${getBackendBase()}/meta`);
        const data = await response.json();
        if (data.name === 'Chess GPT') {
          return { passed: true, message: `Version ${data.version}` };
        }
        throw new Error('Invalid response');
      }
    },
    {
      name: 'Engine Metrics',
      run: async () => {
        const response = await fetch(`${getBackendBase()}/engine/metrics`);
        const data = await response.json();
        return { 
          passed: true, 
          message: `${data.total_requests} requests, ${data.failed_requests} failures` 
        };
      }
    },
    {
      name: 'Position Analysis',
      run: async () => {
        const fen = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';
        const response = await fetch(
          `${getBackendBase()}/analyze_position?fen=${encodeURIComponent(fen)}&depth=10&lines=2`
        );
        const data = await response.json();
        if ('eval_cp' in data && 'candidate_moves' in data) {
          return { passed: true, message: `Eval: ${data.eval_cp}cp, ${data.candidate_moves.length} candidates` };
        }
        throw new Error('Missing analysis data');
      }
    },
    {
      name: 'Play Move',
      run: async () => {
        const response = await fetch(`${getBackendBase()}/play_move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
            user_move_san: 'e4',
            engine_elo: 1600,
            time_ms: 1000
          })
        });
        const data = await response.json();
        if (data.legal && data.engine_move_san) {
          return { passed: true, message: `Engine played: ${data.engine_move_san}` };
        }
        throw new Error('Invalid play response');
      }
    },
    {
      name: 'Confidence Tree',
      run: async () => {
        const response = await fetch(`${getBackendBase()}/confidence/raise_move`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
            move_san: 'e4',
            target: 80
          })
        });
        const data = await response.json();
        const conf = data.confidence || data;
        if ('nodes' in conf) {
          return { passed: true, message: `${conf.nodes.length} nodes generated` };
        }
        throw new Error('No nodes in response');
      }
    }
  ];

  const runTest = async (test: typeof tests[0]) => {
    setResults(prev => [
      ...prev.filter(r => r.name !== test.name),
      { name: test.name, status: 'running' }
    ]);

    const startTime = Date.now();

    try {
      const result = await test.run();
      const duration = Date.now() - startTime;
      
      setResults(prev => [
        ...prev.filter(r => r.name !== test.name),
        { 
          name: test.name, 
          status: 'passed', 
          message: result.message,
          duration 
        }
      ]);
    } catch (error: any) {
      const duration = Date.now() - startTime;
      
      setResults(prev => [
        ...prev.filter(r => r.name !== test.name),
        { 
          name: test.name, 
          status: 'failed', 
          message: error.message,
          duration 
        }
      ]);
    }
  };

  const runAllTests = async () => {
    setIsRunning(true);
    setResults([]);
    
    for (const test of tests) {
      await runTest(test);
    }
    
    setIsRunning(false);
  };

  const clearResults = () => {
    setResults([]);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="dev-test-panel-toggle"
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          padding: '10px 20px',
          background: '#333',
          color: '#fff',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer',
          zIndex: 9999,
          fontSize: '14px',
          fontFamily: 'monospace'
        }}
      >
        🧪 Dev Tests
      </button>
    );
  }

  return (
    <div
      className="dev-test-panel"
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        width: '400px',
        maxHeight: '500px',
        background: '#1a1a1a',
        border: '1px solid #333',
        borderRadius: '12px',
        padding: '16px',
        zIndex: 9999,
        fontFamily: 'monospace',
        fontSize: '13px',
        color: '#fff',
        overflow: 'auto',
        boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
        <h3 style={{ margin: 0, fontSize: '16px' }}>🧪 Dev Test Panel</h3>
        <button
          onClick={() => setIsOpen(false)}
          style={{
            background: 'none',
            border: 'none',
            color: '#888',
            cursor: 'pointer',
            fontSize: '20px'
          }}
        >
          ×
        </button>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <button
          onClick={runAllTests}
          disabled={isRunning}
          style={{
            flex: 1,
            padding: '8px',
            background: isRunning ? '#555' : '#0070f3',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: isRunning ? 'not-allowed' : 'pointer',
            fontSize: '12px'
          }}
        >
          {isRunning ? 'Running...' : 'Run All Tests'}
        </button>
        <button
          onClick={clearResults}
          style={{
            padding: '8px 16px',
            background: '#333',
            color: '#fff',
            border: '1px solid #555',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '12px'
          }}
        >
          Clear
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {tests.map(test => {
          const result = results.find(r => r.name === test.name);
          
          return (
            <div
              key={test.name}
              style={{
                background: '#2a2a2a',
                padding: '12px',
                borderRadius: '6px',
                border: `1px solid ${
                  result?.status === 'passed' ? '#0f0' :
                  result?.status === 'failed' ? '#f00' :
                  result?.status === 'running' ? '#ff0' :
                  '#555'
                }`
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 'bold' }}>
                  {result?.status === 'passed' ? '✅' : 
                   result?.status === 'failed' ? '❌' :
                   result?.status === 'running' ? '⏳' : '⚪'}
                  {' '}{test.name}
                </span>
                <button
                  onClick={() => runTest(test)}
                  disabled={isRunning}
                  style={{
                    padding: '4px 12px',
                    background: '#444',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: isRunning ? 'not-allowed' : 'pointer',
                    fontSize: '11px'
                  }}
                >
                  Run
                </button>
              </div>
              
              {result && (
                <div style={{ marginTop: '8px', fontSize: '11px', color: '#aaa' }}>
                  {result.message && <div>{result.message}</div>}
                  {result.duration && <div style={{ marginTop: '4px' }}>⏱️ {result.duration}ms</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: '16px', padding: '12px', background: '#2a2a2a', borderRadius: '6px' }}>
        <div style={{ fontSize: '11px', color: '#888' }}>
          Summary: {results.filter(r => r.status === 'passed').length}/{results.length} passed
        </div>
      </div>
    </div>
  );
}

