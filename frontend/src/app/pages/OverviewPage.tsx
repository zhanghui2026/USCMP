import { useEffect, useState, useMemo, useCallback, memo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Input, Select, Spin, Empty, Tag, Collapse, Button } from 'antd';
import { SearchOutlined, TeamOutlined, DownOutlined } from '@ant-design/icons';
import { getMembers } from '../api/client';
import type { MemberSummary } from '../api/types';
import { useAppStore } from '../store';
import MemberAvatar from '../components/MemberAvatar';

const { Option } = Select;

// Committee classification
const HOUSE_STANDING = [
  'House Committee on Agriculture',
  'House Committee on Appropriations',
  'House Committee on Armed Services',
  'House Committee on Education and Workforce',
  'House Committee on Energy and Commerce',
  'House Committee on Ethics',
  'House Committee on Financial Services',
  'House Committee on Foreign Affairs',
  'House Committee on Homeland Security',
  'House Committee on House Administration',
  'House Committee on Natural Resources',
  'House Committee on Oversight and Government Reform',
  'House Committee on Rules',
  'House Committee on Science, Space, and Technology',
  'House Committee on Small Business',
  'House Committee on Transportation and Infrastructure',
  'House Committee on Veterans\' Affairs',
  'House Committee on Ways and Means',
  'House Committee on the Budget',
  'House Committee on the Judiciary',
];

const HOUSE_SELECT = [
  'House Permanent Select Committee on Intelligence',
  'House Select Committee on the Strategic Competition Between the United States and the Chinese Communist Party',
];

const SENATE_STANDING = [
  'Senate Committee on Agriculture, Nutrition, and Forestry',
  'Senate Committee on Appropriations',
  'Senate Committee on Armed Services',
  'Senate Committee on Banking, Housing, and Urban Affairs',
  'Senate Committee on Commerce, Science, and Transportation',
  'Senate Committee on Energy and Natural Resources',
  'Senate Committee on Environment and Public Works',
  'Senate Committee on Finance',
  'Senate Committee on Foreign Relations',
  'Senate Committee on Health, Education, Labor, and Pensions',
  'Senate Committee on Homeland Security and Governmental Affairs',
  'Senate Committee on Indian Affairs',
  'Senate Committee on Rules and Administration',
  'Senate Committee on Small Business and Entrepreneurship',
  'Senate Committee on Veterans\' Affairs',
  'Senate Committee on the Budget',
  'Senate Committee on the Judiciary',
];

const SENATE_SPECIAL = [
  'Senate Select Committee on Ethics',
  'Senate Select Committee on Intelligence',
  'Senate Special Committee on Aging',
  'United States Senate Caucus on International Narcotics Control',
];

const JOINT_COMMITTEES = [
  'Commission on Security and Cooperation in Europe',
  'Joint Committee of Congress on the Library',
  'Joint Committee on Printing',
  'Joint Committee on Taxation',
  'Joint Economic Committee',
];

const INITIAL_DISPLAY_COUNT = 12;

type CommitteeMember = MemberSummary & { currentCommittee?: string };

function getCommitteeCategory(committee: string): string {
  if (HOUSE_STANDING.includes(committee)) return 'house_standing';
  if (HOUSE_SELECT.includes(committee)) return 'house_select';
  if (SENATE_STANDING.includes(committee)) return 'senate_standing';
  if (SENATE_SPECIAL.includes(committee)) return 'senate_special';
  if (JOINT_COMMITTEES.includes(committee)) return 'joint';
  return 'other';
}

function getCommitteeCategoryLabel(category: string): string {
  switch (category) {
    case 'house_standing': return '常设委员会';
    case 'house_select': return '专门委员会';
    case 'senate_standing': return '常设委员会';
    case 'senate_special': return '特别/专门委员会';
    case 'joint': return '两院联合委员会';
    default: return '其他';
  }
}

function getChamberLabel(chamber?: string) {
  return chamber === 'senate' ? '参议院' : chamber === 'house' ? '众议院' : '';
}

function getPartyLabel(party?: string) {
  return party === 'Democratic' ? '民主党' : party === 'Republican' ? '共和党' : party === 'Independent' ? '独立' : party || '';
}

function highlightText(text: string, keyword: string) {
  if (!keyword.trim()) return text;
  const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span style={{ background: '#fbbf24', color: '#1f2937', borderRadius: 2, padding: '0 2px' }}>{text.slice(idx, idx + keyword.length)}</span>
      {text.slice(idx + keyword.length)}
    </>
  );
}

interface GroupedMembers {
  [committee: string]: CommitteeMember[];
}

interface CategorizedMembers {
  [category: string]: GroupedMembers;
}

function groupByCommitteeAndCategory(members: MemberSummary[]): { categorized: CategorizedMembers; withoutCommittee: MemberSummary[] } {
  const categorized: CategorizedMembers = {};
  const withoutCommittee: MemberSummary[] = [];

  for (const m of members) {
    if (m.committee_tags.length > 0) {
      const uniqueCommittees = Array.from(new Set(m.committee_tags));
      for (const committee of uniqueCommittees) {
        const category = getCommitteeCategory(committee);

        if (!categorized[category]) categorized[category] = {};
        if (!categorized[category][committee]) categorized[category][committee] = [];
        categorized[category][committee].push({ ...m, currentCommittee: committee });
      }
    } else {
      withoutCommittee.push(m);
    }
  }

  for (const category of Object.keys(categorized)) {
    const sorted: GroupedMembers = {};
    for (const key of Object.keys(categorized[category]).sort()) {
      sorted[key] = categorized[category][key];
    }
    categorized[category] = sorted;
  }

  return { categorized, withoutCommittee };
}

// Memoized MemberCard - only re-renders when props change
const MemberCard = memo(function MemberCard({ m, search, partyColorMap }: { m: CommitteeMember; search: string; partyColorMap: Record<string, string> }) {
  const navigate = useNavigate();
  const handleClick = useCallback(() => navigate(`/member/${m.id}`), [navigate, m.id]);
  const committeeLabel = m.currentCommittee || m.committee_tags[0];

  return (
    <div
      onClick={handleClick}
      style={{
        background: '#1a1a2e',
        borderRadius: 10,
        padding: 16,
        cursor: 'pointer',
        borderLeft: `3px solid ${partyColorMap[m.party || ''] || '#6b7280'}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = '0 4px 15px rgba(0,0,0,0.3)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <MemberAvatar image_url={m.image_url} display_name={m.display_name} party={m.party} size={40} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#e5e7eb', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {search ? highlightText(m.display_name, search) : m.display_name}
        </div>
        <div style={{ fontSize: 11, color: '#9ca3af' }}>
          <span style={{ color: partyColorMap[m.party || ''] || '#9ca3af' }}>{getPartyLabel(m.party)}</span>
          <span style={{ margin: '0 3px' }}>|</span>
          {getChamberLabel(m.chamber)}
          {m.state ? <><span style={{ margin: '0 3px' }}>|</span>{m.state}</> : null}
        </div>
      </div>
      {committeeLabel && (
        <Tag color="blue" style={{ fontSize: 9, margin: 0, borderRadius: 3, lineHeight: '16px', flexShrink: 0 }}>
          {committeeLabel.length > 12 ? committeeLabel.slice(0, 12) + '...' : committeeLabel}
        </Tag>
      )}
    </div>
  );
});

// Lazy committee section - only renders cards when expanded
function CommitteeSection({ title, members, search, partyColorMap, defaultOpen = false }: {
  title: string; members: CommitteeMember[]; search: string; partyColorMap: Record<string, string>; defaultOpen?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultOpen);
  const [showAll, setShowAll] = useState(false);
  const displayedMembers = showAll ? members : members.slice(0, INITIAL_DISPLAY_COUNT);
  const hasMore = members.length > INITIAL_DISPLAY_COUNT;

  return (
    <Collapse
      defaultActiveKey={defaultOpen ? ['1'] : []}
      onChange={(keys) => setExpanded(keys.length > 0)}
      style={{ background: 'transparent', border: 'none', marginBottom: 8 }}
      expandIconPosition="end"
      items={[{
        key: '1',
        label: (
          <span style={{ color: '#d1d5db', fontSize: 13, fontWeight: 500 }}>
            <TeamOutlined style={{ marginRight: 6, color: '#6b7280' }} />
            {title}
            <Tag style={{ marginLeft: 8, fontSize: 10 }}>{members.length}</Tag>
          </span>
        ),
        children: expanded ? (
          <>
            <Row gutter={[10, 10]}>
              {displayedMembers.map((m) => (
                <Col key={m.id} xs={24} sm={12} md={8} lg={6}>
                  <MemberCard m={m} search={search} partyColorMap={partyColorMap} />
                </Col>
              ))}
            </Row>
            {hasMore && !showAll && (
              <div style={{ textAlign: 'center', marginTop: 12 }}>
                <Button
                  type="link"
                  size="small"
                  icon={<DownOutlined />}
                  onClick={(e) => { e.stopPropagation(); setShowAll(true); }}
                  style={{ color: '#6b7280', fontSize: 11 }}
                >
                  显示更多 ({members.length - INITIAL_DISPLAY_COUNT} 人)
                </Button>
              </div>
            )}
          </>
        ) : null,
        style: { background: '#111827', border: '1px solid #1f2937', borderRadius: 8 },
      }]}
    />
  );
}

function CategorySection({ categoryLabel, committees, search, partyColorMap, defaultOpen = false }: {
  categoryLabel: string; committees: GroupedMembers; search: string; partyColorMap: Record<string, string>; defaultOpen?: boolean;
}) {
  const committeeKeys = Object.keys(committees);
  const totalMembers = committeeKeys.reduce((sum, key) => sum + committees[key].length, 0);

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 8, 
        marginBottom: 8,
        padding: '8px 12px',
        background: '#0f1320',
        borderRadius: 6,
        border: '1px solid #1f2937'
      }}>
        <span style={{ color: '#9ca3af', fontSize: 12, fontWeight: 500 }}>
          {categoryLabel}
        </span>
        <Tag style={{ fontSize: 10 }}>{totalMembers} 人</Tag>
      </div>
      {committeeKeys.map((cmte) => (
        <CommitteeSection
          key={cmte}
          title={cmte}
          members={committees[cmte]}
          search={search}
          partyColorMap={partyColorMap}
          defaultOpen={defaultOpen}
        />
      ))}
    </div>
  );
}

export default function OverviewPage() {
  const { members, setMembers, setError, loading, setLoading, totalMembers } = useAppStore();
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
      const result = await getMembers({ limit: 600, ...filter });
      setMembers(result.members, result.total);
    } catch {
      setError('加载议员列表失败');
    } finally {
      setLoading(false);
    }
  };

  const partyColorMap: Record<string, string> = {
    Republican: '#f5222d',
    Democratic: '#1890ff',
    Independent: '#8c8c8c',
  };

  const filtered = useMemo(() => {
    if (!filter.search.trim()) return members;
    const q = filter.search.toLowerCase();
    return members.filter((m) => m.display_name.toLowerCase().includes(q));
  }, [members, filter.search]);

  const senateMembers = useMemo(() => filtered.filter((m) => m.chamber === 'senate'), [filtered]);
  const houseMembers = useMemo(() => filtered.filter((m) => m.chamber === 'house'), [filtered]);

  const senateGrouped = useMemo(() => groupByCommitteeAndCategory(senateMembers), [senateMembers]);
  const houseGrouped = useMemo(() => groupByCommitteeAndCategory(houseMembers), [houseMembers]);

  const renderChamber = (chamberLabel: string, grouped: ReturnType<typeof groupByCommitteeAndCategory>, count: number) => {
    const categories = Object.keys(grouped.categorized);
    const hasContent = categories.length > 0 || grouped.withoutCommittee.length > 0;
    if (!hasContent) return null;

    const categoryOrder = chamberLabel === '众议院' 
      ? ['house_standing', 'house_select'] 
      : ['senate_standing', 'senate_special'];
    
    const sortedCategories = categoryOrder.filter(c => grouped.categorized[c]);

    return (
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <h2 style={{ color: '#e5e7eb', fontSize: 16, fontWeight: 600, margin: 0 }}>
            {chamberLabel}
          </h2>
          <Tag style={{ fontSize: 11 }}>{count} 人</Tag>
        </div>

        {sortedCategories.map((category) => (
          <CategorySection
            key={category}
            categoryLabel={getCommitteeCategoryLabel(category)}
            committees={grouped.categorized[category]}
            search={filter.search}
            partyColorMap={partyColorMap}
            defaultOpen={false}
          />
        ))}

        {grouped.withoutCommittee.length > 0 && (
          <CommitteeSection
            title="无委员会任职"
            members={grouped.withoutCommittee}
            search={filter.search}
            partyColorMap={partyColorMap}
            defaultOpen={false}
          />
        )}
      </div>
    );
  };

  return (
    <div style={{ padding: '24px 40px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <h1 style={{ color: '#e5e7eb', fontSize: 18, fontWeight: 600, margin: 0 }}>
            美国国会利益关联图谱
          </h1>
          <span style={{ color: '#6b7280', fontSize: 12 }}>
            共 {totalMembers} 位议员
          </span>
        </div>
        <Row gutter={12} align="middle">
          <Col span={8}>
            <Input
              prefix={<SearchOutlined style={{ color: '#6b7280' }} />}
              placeholder="搜索议员姓名..."
              value={filter.search}
              onChange={(e) => setFilter({ ...filter, search: e.target.value })}
              onPressEnter={loadMembers}
              style={{ background: '#1f2937', border: '1px solid #374151', color: '#e5e7eb' }}
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
          <Col span={3}>
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
        {filtered.length === 0 && !loading ? (
          <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <>
            {renderChamber('参议院', senateGrouped, senateMembers.length)}
            {renderChamber('众议院', houseGrouped, houseMembers.length)}
          </>
        )}
      </Spin>
    </div>
  );
}
