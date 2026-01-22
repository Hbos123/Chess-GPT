"use client";

/**
 * MarkdownTable Component
 * Parses markdown table syntax and renders as proper HTML table
 */

interface MarkdownTableProps {
  content: string;
}

export default function MarkdownTable({ content }: MarkdownTableProps) {
  const lines = content.trim().split('\n');
  
  if (lines.length < 2) return <pre>{content}</pre>;
  
  // Extract headers (first line)
  const headers = lines[0]
    .split('|')
    .map(h => h.trim())
    .filter(h => h.length > 0);
  
  // Skip separator line (line 1)
  
  // Extract rows (lines 2+)
  const rows = lines.slice(2).map(line => 
    line.split('|')
      .map(cell => cell.trim())
      .filter(cell => cell.length > 0)
  );
  
  return (
    <div className="markdown-table-container" style={{ 
      overflowX: 'auto', 
      margin: '1rem 0',
      borderRadius: '8px',
      border: '1px solid #333'
    }}>
      <table style={{
        width: '100%',
        borderCollapse: 'collapse',
        backgroundColor: '#1a1a1a',
        color: '#e5e5e5'
      }}>
        <thead>
          <tr style={{ backgroundColor: '#2a2a2a' }}>
            {headers.map((header, i) => (
              <th key={i} style={{
                padding: '12px 16px',
                textAlign: 'left',
                fontWeight: 600,
                borderBottom: '2px solid #444',
                fontSize: '0.9rem',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} style={{
              backgroundColor: rowIndex % 2 === 0 ? '#1a1a1a' : '#222',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#2a2a2a'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = rowIndex % 2 === 0 ? '#1a1a1a' : '#222'}
            >
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} style={{
                  padding: '10px 16px',
                  borderBottom: '1px solid #333',
                  fontSize: '0.9rem'
                }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}




