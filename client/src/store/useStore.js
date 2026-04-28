import { create } from 'zustand'

const useStore = create((set, get) => ({
  // Detection state
  detectionResult: null,
  isDetecting: false,
  detectionBbox: '31.0,-104.0,33.0,-102.0',
  detectionDate: '',
  simulationMode: true,

  // Facilities
  facilities: [],
  topPolluters: [],
  selectedFacility: null,

  // Alerts
  alerts: [],
  liveAlerts: [],
  alertFilter: null,

  // Heatmap
  heatmapData: null,

  // Simulation (plume spread)
  simulationParams: {
    source_lat: 31.8,
    source_lon: -103.5,
    emission_rate_kg_hr: 500,
    wind_speed_ms: 5.0,
    wind_direction_deg: 270,
    duration_minutes: 120,
    timestep_minutes: 10,
  },
  simulationResult: null,
  currentSimFrame: 0,
  isSimPlaying: false,

  // UI state
  activeTab: 'globe',
  sidebarOpen: true,

  // Timeseries
  timeseriesData: null,
  globalTimeseries: null,

  // Actions
  setDetectionBbox: (bbox) => set({ detectionBbox: bbox }),
  setDetectionDate: (date) => set({ detectionDate: date }),
  setSimulationMode: (v) => set({ simulationMode: v }),
  setDetectionResult: (r) => set({ detectionResult: r }),
  setIsDetecting: (v) => set({ isDetecting: v }),

  setFacilities: (f) => set({ facilities: f }),
  setTopPolluters: (p) => set({ topPolluters: p }),
  setSelectedFacility: (f) => set({ selectedFacility: f }),

  setAlerts: (a) => set({ alerts: a }),
  pushLiveAlert: (alert) => set(state => ({
    liveAlerts: [alert, ...state.liveAlerts].slice(0, 50)
  })),
  setAlertFilter: (f) => set({ alertFilter: f }),

  setHeatmapData: (d) => set({ heatmapData: d }),

  setSimulationParams: (p) => set(state => ({
    simulationParams: { ...state.simulationParams, ...p }
  })),
  setSimulationResult: (r) => set({ simulationResult: r, currentSimFrame: 0 }),
  setCurrentSimFrame: (f) => set({ currentSimFrame: f }),
  setIsSimPlaying: (v) => set({ isSimPlaying: v }),

  setActiveTab: (tab) => set({ activeTab: tab }),
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
  setTimeseriesData: (d) => set({ timeseriesData: d }),
  setGlobalTimeseries: (d) => set({ globalTimeseries: d }),
}))

export default useStore
