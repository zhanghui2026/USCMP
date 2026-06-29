import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout, Menu, Tag, Tooltip } from 'antd';
import { TeamOutlined, SearchOutlined, BarChartOutlined, HomeOutlined, DashboardOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import OverviewPage from './pages/OverviewPage';
import MemberDetailPage from './pages/MemberDetailPage';
import SearchPage from './pages/SearchPage';
import ComparePage from './pages/ComparePage';
import DataQualityPage from './pages/DataQualityPage';
import { getHealth } from './api/client';
import { DATA_MODE_COLORS, DATA_MODE_LABELS, DATA_MODE_TOOLTIPS } from './constants';

const { Header, Content } = Layout;

const menuItems = [
  { key: '/', icon: <HomeOutlined />, label: '概览' },
  { key: '/search', icon: <SearchOutlined />, label: '搜索' },
  { key: '/compare', icon: <BarChartOutlined />, label: '对比' },
  { key: '/data-quality', icon: <DashboardOutlined />, label: '数据质量' },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [dataMode, setDataMode] = useState<string>('unknown');
  const selectedKey = location.pathname.startsWith('/member/')
    ? '/' : location.pathname;

  useEffect(() => {
    getHealth().then((h) => setDataMode(h.data_mode || 'unknown')).catch(() => {});
  }, []);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px', height: 56 }}>
        <div style={{ color: '#1890ff', fontWeight: 700, fontSize: 18, marginRight: 24, whiteSpace: 'nowrap' }}>
          Congress Interest Graph
        </div>
        <Tooltip title={DATA_MODE_TOOLTIPS[dataMode] || '数据模式'}>
          <Tag color={DATA_MODE_COLORS[dataMode] || 'default'} style={{ marginRight: 16, fontSize: 11, cursor: 'help' }}>
            {DATA_MODE_LABELS[dataMode] || '?'}
          </Tag>
        </Tooltip>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ flex: 1, background: 'transparent', borderBottom: 'none' }}
        />
      </Header>
      <Content style={{ padding: 0, height: 'calc(100vh - 56px)', overflow: 'auto' }}>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/member/:id" element={<MemberDetailPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/data-quality" element={<DataQualityPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}
