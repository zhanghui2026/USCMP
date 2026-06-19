import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, Input, Select, Tag, Spin, Empty } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { getMembers } from '../api/client';
import type { MemberSummary } from '../api/types';
import { useAppStore } from '../store';
import { getPartyColor } from '../constants';
import MemberAvatar from '../components/MemberAvatar';

const { Option } = Select;

const SOURCE_BADGES: Record<string, { color: string; label: string }> = {
  uscl: { color: 'green', label: '真实' },
  mock: { color: 'orange', label: 'Mock' },
};

export default function OverviewPage() {
  const navigate = useNavigate();
  const { members, setMembers, setError, loading, setLoading } = useAppStore();
  const [filter, setFilter] = useState({
    chamber: undefined as string | undefined,
    party: undefined as string | undefined,
    congress: undefined as number | undefined,
    search: '',
  });

  useEffect(() => {
    loadMembers();
  }, []);

  const loadMembers = async () => {
    setLoading(true);
    try {
      const result = await getMembers({ limit: 200, ...filter });
      setMembers(result.members, result.total);
    } catch (e) {
      setError('Failed to load members');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#e5e7eb', fontSize: 24, marginBottom: 16 }}>美国国会利益关联图谱</h1>
        <Row gutter={12} align="middle">
          <Col span={6}>
            <Input
              prefix={<SearchOutlined />}
              placeholder="搜索议员姓名..."
              value={filter.search}
              onChange={(e) => setFilter({ ...filter, search: e.target.value })}
              onPressEnter={loadMembers}
            />
          </Col>
          <Col span={4}>
            <Select
              placeholder="议院"
              allowClear
              style={{ width: '100%' }}
              value={filter.chamber}
              onChange={(v) => setFilter({ ...filter, chamber: v })}
            >
              <Option value="senate">参议院</Option>
              <Option value="house">众议院</Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="党派"
              allowClear
              style={{ width: '100%' }}
              value={filter.party}
              onChange={(v) => setFilter({ ...filter, party: v })}
            >
              <Option value="Democratic">民主党</Option>
              <Option value="Republican">共和党</Option>
              <Option value="Independent">独立</Option>
            </Select>
          </Col>
          <Col span={4}>
            <Select
              placeholder="届次"
              allowClear
              style={{ width: '100%' }}
              value={filter.congress}
              onChange={(v) => setFilter({ ...filter, congress: v })}
            >
              <Option value={117}>第 117 届</Option>
              <Option value={118}>第 118 届</Option>
              <Option value={119}>第 119 届</Option>
            </Select>
          </Col>
        </Row>
      </div>

      <Spin spinning={loading}>
        {members.length === 0 && !loading ? (
          <Empty description="暂无数据" />
        ) : (
          <Row gutter={[16, 16]}>
            {members.map((m) => (
              <Col key={m.id} xs={24} sm={12} md={8} lg={6} xl={4}>
                <Card
                  hoverable
                  size="small"
                  onClick={() => navigate(`/member/${m.id}`)}
                  style={{ cursor: 'pointer', borderTop: `3px solid ${getPartyColor(m.party)}` }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <MemberAvatar image_url={m.image_url} display_name={m.display_name} party={m.party} size={32} />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.2 }}>{m.display_name}</div>
                      <div style={{ fontSize: 11, color: '#9ca3af' }}>
                        {m.party} | {m.state} {m.chamber === 'senate' ? '参议院' : '众议院'}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 4 }}>
                    {m.committee_tags.slice(0, 3).map((tag, i) => (
                      <Tag key={i} color="blue" style={{ fontSize: 10, margin: 0 }}>{tag}</Tag>
                    ))}
                    {m.committee_tags.length > 3 && (
                      <Tag style={{ fontSize: 10, margin: 0 }}>+{m.committee_tags.length - 3}</Tag>
                    )}
                  </div>
                  {(SOURCE_BADGES[m.source] || SOURCE_BADGES.mock) && (
                    <Tag
                      color={(SOURCE_BADGES[m.source] || SOURCE_BADGES.mock).color}
                      style={{ fontSize: 10, margin: 0 }}
                    >
                      {(SOURCE_BADGES[m.source] || SOURCE_BADGES.mock).label}
                    </Tag>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );
}
