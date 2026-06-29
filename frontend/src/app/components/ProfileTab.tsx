import { Card, Empty, Typography, Table, Tag } from 'antd';
import { BulbOutlined, ExperimentOutlined, GlobalOutlined } from '@ant-design/icons';

const { Text, Paragraph } = Typography;

interface Props {
  china_stance_summary?: string;
  core_positions?: string;
  comprehensive_evaluation?: string;
}

function parseMarkdownTable(text: string): { columns: any[]; data: any[] } | null {
  const lines = text.trim().split('\n').filter(l => l.trim());
  if (lines.length < 2) return null;

  const headerLine = lines[0];
  const separatorLine = lines[1];
  if (!headerLine.includes('|') || !separatorLine.includes('---')) return null;

  const headers = headerLine.split('|').map(h => h.trim()).filter(Boolean);
  const dataLines = lines.slice(2);

  const columns = headers.map((h, i) => ({
    title: h.replace(/\*\*/g, ''),
    dataIndex: `col${i}`,
    key: `col${i}`,
    render: (text: string) => {
      if (!text) return null;
      const clean = text.replace(/\*\*/g, '');
      return <span style={{ fontSize: 11 }}>{clean}</span>;
    },
  }));

  const data = dataLines.map((line, idx) => {
    const cells = line.split('|').map(c => c.trim()).filter(Boolean);
    const row: any = { key: idx };
    headers.forEach((_, i) => {
      row[`col${i}`] = cells[i] || '';
    });
    return row;
  });

  return { columns, data };
}

function renderStructuredContent(text: string) {
  if (!text) return <Text type="secondary" style={{ fontSize: 11, fontStyle: 'italic' }}>暂无数据</Text>;

  const tableResult = parseMarkdownTable(text);
  if (tableResult) {
    return (
      <Table
        columns={tableResult.columns}
        dataSource={tableResult.data}
        pagination={false}
        size="small"
        bordered
        style={{ fontSize: 11 }}
      />
    );
  }

  const paragraphs = text.split('\n').filter(p => p.trim());
  return (
    <div style={{ color: '#d1d5db', fontSize: 12, lineHeight: 1.8 }}>
      {paragraphs.map((p, i) => {
        const clean = p.replace(/\*\*/g, '');
        if (clean.startsWith('**') || clean.match(/^[•\-]/)) {
          return <div key={i} style={{ marginBottom: 4 }}>{clean}</div>;
        }
        return <Paragraph key={i} style={{ color: '#d1d5db', fontSize: 12, marginBottom: 8 }}>{clean}</Paragraph>;
      })}
    </div>
  );
}

export default function ProfileTab({ china_stance_summary, core_positions, comprehensive_evaluation }: Props) {
  const hasData = china_stance_summary || core_positions || comprehensive_evaluation;

  if (!hasData) {
    return <Empty description="暂无政治画像数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div style={{ padding: 0 }}>
      {china_stance_summary && (
        <Card
          size="small"
          title={<span><GlobalOutlined style={{ marginRight: 6 }} />对华立场</span>}
          style={{ marginBottom: 8, background: '#1a1a2e' }}
        >
          {renderStructuredContent(china_stance_summary)}
        </Card>
      )}

      {core_positions && (
        <Card
          size="small"
          title={<span><BulbOutlined style={{ marginRight: 6 }} />核心政治主张</span>}
          style={{ marginBottom: 8, background: '#1a1a2e' }}
        >
          {renderStructuredContent(core_positions)}
        </Card>
      )}

      {comprehensive_evaluation && (
        <Card
          size="small"
          title={<span><ExperimentOutlined style={{ marginRight: 6 }} />综合评价</span>}
          style={{ marginBottom: 8, background: '#1a1a2e' }}
        >
          <div style={{ color: '#d1d5db', fontSize: 12, lineHeight: 1.8 }}>
            {comprehensive_evaluation.split('\n').filter(p => p.trim()).map((p, i) => {
              const clean = p.replace(/\*\*/g, '');
              return <div key={i} style={{ marginBottom: 6 }}>{clean}</div>;
            })}
          </div>
        </Card>
      )}

      <div style={{ fontSize: 10, color: '#6b7280', textAlign: 'right', marginTop: 4 }}>
        数据来源: 国会成员画像集 (2025)
      </div>
    </div>
  );
}
