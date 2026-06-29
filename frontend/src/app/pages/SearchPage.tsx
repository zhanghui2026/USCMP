import { useState } from 'react';
import { Input, Card, Tag, Empty, Spin, List, Tabs, message } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { search } from '../api/client';
import type { MemberSummary, OrganizationSummary, EventModel } from '../api/types';
import { getPartyColor } from '../constants';

const SOURCE_BADGES: Record<string, { color: string; label: string }> = {
  uscl: { color: 'green', label: '真实' },
  mock: { color: 'orange', label: 'Mock' },
};

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<{ members: MemberSummary[]; organizations: OrganizationSummary[]; events: EventModel[]; total_count: number } | null>(null);

  const doSearch = async () => {
    if (query.trim().length < 2) {
      message.warning('搜索关键词至少 2 个字符');
      return;
    }
    setLoading(true);
    try {
      const r = await search({ query: query.trim(), limit: 50 });
      setResults(r);
    } catch (e) {
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>全局搜索</h1>
      <Input.Search
        size="large"
        placeholder="搜索议员、组织、事件..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onSearch={doSearch}
        enterButton
        style={{ marginBottom: 24 }}
      />

      <Spin spinning={loading}>
        {results && results.total_count === 0 ? (
          <Empty description="未找到结果" />
        ) : results ? (
          <Tabs
            items={[
              {
                key: 'members',
                label: `议员 (${results.members.length})`,
                children: (
                  <List
                    dataSource={results.members}
                    renderItem={(m: MemberSummary) => (
                      <Card
                        hoverable
                        size="small"
                        style={{ marginBottom: 8, cursor: 'pointer' }}
                        onClick={() => navigate(`/member/${m.id}`)}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{
                            width: 36, height: 36, borderRadius: '50%', background: getPartyColor(m.party),
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: '#fff', fontWeight: 700,
                          }}>
                            {m.canonical_name.charAt(0)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600 }}>{m.display_name}</div>
                            <div style={{ fontSize: 12, color: '#9ca3af' }}>
                              {m.party} | {m.state} | {m.chamber === 'senate' ? '参议院' : '众议院'}
                              {(SOURCE_BADGES[m.source] || SOURCE_BADGES.mock) && (
                                <Tag
                                  color={(SOURCE_BADGES[m.source] || SOURCE_BADGES.mock).color}
                                  style={{ fontSize: 10, marginLeft: 4 }}
                                >
                                  {(SOURCE_BADGES[m.source] || SOURCE_BADGES.mock).label}
                                </Tag>
                              )}
                            </div>
                          </div>
                        </div>
                      </Card>
                    )}
                  />
                ),
              },
              {
                key: 'orgs',
                label: `组织 (${results.organizations.length})`,
                children: (
                  <List
                    dataSource={results.organizations}
                    renderItem={(o: OrganizationSummary) => (
                      <Card size="small" style={{ marginBottom: 8 }}>
                        <div style={{ fontWeight: 600 }}>{o.display_name}</div>
                        <div style={{ fontSize: 12, color: '#9ca3af' }}>
                          <Tag color="purple">{o.entity_type}</Tag>
                          {o.industry} | {o.ticker || 'N/A'}
                        </div>
                      </Card>
                    )}
                  />
                ),
              },
              {
                key: 'events',
                label: `事件 (${results.events.length})`,
                children: (
                  <List
                    dataSource={results.events}
                    renderItem={(e: EventModel) => (
                      <Card size="small" style={{ marginBottom: 8 }}>
                        <div style={{ fontWeight: 600 }}>{e.title}</div>
                        <div style={{ fontSize: 12, color: '#9ca3af' }}>
                          <Tag>{e.event_type}</Tag>
                          {e.event_date} | 第{e.congress}届
                        </div>
                      </Card>
                    )}
                  />
                ),
              },
            ]}
          />
        ) : null}
      </Spin>
    </div>
  );
}
