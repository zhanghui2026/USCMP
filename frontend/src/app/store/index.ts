import { create } from 'zustand';
import type { MemberSummary, MemberDetail, GraphResponse } from '../api/types';

interface AppState {
  members: MemberSummary[];
  totalMembers: number;
  selectedMember: MemberDetail | null;
  graphData: GraphResponse | null;
  timeRange: [string, string];
  loading: boolean;
  error: string | null;

  // Actions
  setMembers: (members: MemberSummary[], total: number) => void;
  setSelectedMember: (member: MemberDetail | null) => void;
  setGraphData: (graph: GraphResponse | null) => void;
  setTimeRange: (range: [string, string]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  members: [],
  totalMembers: 0,
  selectedMember: null,
  graphData: null,
  timeRange: ['2019-01-01', '2026-12-31'],
  loading: false,
  error: null,

  setMembers: (members, total) => set({ members, totalMembers: total }),
  setSelectedMember: (member) => set({ selectedMember: member }),
  setGraphData: (graph) => set({ graphData: graph }),
  setTimeRange: (range) => set({ timeRange: range }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
