import { Card, Tag, Empty, Typography } from 'antd';
import {
  ExclamationCircleOutlined,
  FileSearchOutlined,
  BankOutlined,
  LinkOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

interface ControversyItem {
  type?: string;
  description?: string;
  source_name?: string;
  source_url?: string;
  published_at?: string;
  snippet?: string;
  status?: string;
  official_confirmed?: boolean;
  judicial_confirmed?: boolean;
  needs_review?: boolean;
}

interface Props {
  controversies: Record<string, unknown>[];
}

function getTypeIcon(type: string) {
  switch (type) {
    case 'allegation':
      return <ExclamationCircleOutlined />;
    case 'investigation':
      return <FileSearchOutlined />;
    case 'lawsuit':
      return <BankOutlined />;
    default:
      return <ExclamationCircleOutlined />;
  }
}

function getTypeLabel(type: string) {
  switch (type) {
    case 'allegation':
      return '指控';
    case 'investigation':
      return '调查';
    case 'lawsuit':
      return '诉讼';
    default:
      return type;
  }
}

function getStatusColor(status: string) {
  switch (status) {
    case 'ongoing':
      return 'orange';
    case 'resolved':
      return 'green';
    case 'dismissed':
      return 'default';
    default:
      return 'default';
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'ongoing':
      return '进行中';
    case 'resolved':
      return '已解决';
    case 'dismissed':
      return '已驳回';
    default:
      return status;
  }
}

export default function ControversiesTab({ controversies }: Props) {
  if (!controversies || controversies.length === 0) {
    return <Empty description="暂无媒体争议数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div>
      {controversies.map((item, i) => {
        const c = item as unknown as ControversyItem;
        return (
          <Card
            key={i}
            size="small"
            style={{ marginBottom: 8, background: '#1a1a2e' }}
            styles={{ body: { padding: 12 } }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <div style={{ marginTop: 1, color: '#f59e0b', fontSize: 14 }}>
                {getTypeIcon(c.type || '')}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
                  <Tag icon={getTypeIcon(c.type || '')} color="orange" style={{ fontSize: 10, margin: 0 }}>
                    {getTypeLabel(c.type || 'allegation')}
                  </Tag>
                  {c.status && (
                    <Tag color={getStatusColor(c.status)} style={{ fontSize: 10, margin: 0 }}>
                      {getStatusLabel(c.status)}
                    </Tag>
                  )}
                  {c.official_confirmed && <Tag color="red" style={{ fontSize: 10, margin: 0 }}>官方确认</Tag>}
                  {c.judicial_confirmed && <Tag color="volcano" style={{ fontSize: 10, margin: 0 }}>司法确认</Tag>}
                  {c.needs_review && <Tag color="default" style={{ fontSize: 10, margin: 0 }}>待复核</Tag>}
                </div>

                {c.description && (
                  <div style={{ color: '#d1d5db', fontSize: 12, lineHeight: 1.5, marginBottom: 6 }}>
                    {c.description}
                  </div>
                )}

                {c.snippet && (
                  <div style={{
                    fontSize: 11, color: '#6b7280', fontStyle: 'italic',
                    background: '#0f1320', padding: '6px 8px', borderRadius: 4, marginBottom: 6,
                  }}>
                    {c.snippet}
                  </div>
                )}

                <div style={{ fontSize: 10, color: '#6b7280', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {c.source_name && <span>来源: {c.source_name}</span>}
                  {c.published_at && <span>日期: {c.published_at}</span>}
                  {c.source_url && (
                    <a href={c.source_url} target="_blank" rel="noopener noreferrer" style={{ color: '#1890ff' }}>
                      <LinkOutlined /> 原文链接
                    </a>
                  )}
                </div>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}