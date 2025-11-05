import { useState, useEffect, useRef } from 'react';
import '@/App.css';
import axios from 'axios';
import { Wifi, Zap, Globe, Lock, Activity, Satellite, Radio, Network } from 'lucide-react';
import { ensureRewardGate } from '@/lib/adGate';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const API = `${BACKEND_URL}/api`;

function App() {
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState('idle');
  const [connections, setConnections] = useState([]);
  const [activeConnection, setActiveConnection] = useState(null);
  const [discoveredCount, setDiscoveredCount] = useState(0);
  const [browserUrl, setBrowserUrl] = useState('https://www.google.com');
  const [browserContent, setBrowserContent] = useState('');
  const [showBrowser, setShowBrowser] = useState(false);
  const [stats, setStats] = useState({
    active: 0,
    available: 0,
    latency: 0
  });

  // Auto-check status on load
  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const checkStatus = async () => {
    try {
      const response = await axios.get(`${API}/status`);
      const data = response.data;
      setStats({
        active: data.active_connections,
        available: data.available_connections
      });
      if (data.active_connections > 0) {
        setConnected(true);
        setActiveConnection(data.connections[0]);
      }
    } catch (error) {
      console.error('Status check failed:', error);
    }
  };

  const discoverConnections = async () => {
    setStatus('discovering');
    try {
      const response = await axios.get(`${API}/discover`);
      setConnections(response.data);
      setDiscoveredCount(response.data.length);
      setStatus('discovered');
    } catch (error) {
      console.error('Discovery failed:', error);
      setStatus('error');
    }
  };

  const connectToInternet = async () => {
    setConnecting(true);
    setStatus('connecting');
    
    try {
      // First discover sources
      await discoverConnections();
      
      // Then auto-connect to best one
      const response = await axios.post(`${API}/connect`);
      
      if (response.data.success) {
        setConnected(true);
        setActiveConnection(response.data.connection);
        setStatus('connected');
        await checkStatus();
      } else {
        setStatus('failed');
      }
    } catch (error) {
      console.error('Connection failed:', error);
      setStatus('failed');
    } finally {
      setConnecting(false);
    }
  };

  const loadWebpage = async () => {
    if (!connected) {
      alert('Please connect to internet first!');
      return;
    }
    setStatus('loading');
    try {
      const response = await axios.post(`${API}/proxy`, {
        url: browserUrl,
        method: 'GET',
      });
      const base64 = response?.data?.content || response?.data?.body || '';
      const decoded = base64 ? atob(base64) : '<div>Empty response</div>';
      setBrowserContent(decoded);
      setShowBrowser(true);
      setStatus('browsing');
    } catch (error) {
      console.error('Failed to load webpage:', error);
      setBrowserContent(`<div class="p-4 text-red-700">Failed to load: ${error.message}</div>`);
      setShowBrowser(true);
      setStatus('error');
    }
  };

  const handleConnectClicked = async () => {
    // Gate the connect action behind a rewarded ad
    const unlocked = await ensureRewardGate();
    if (!unlocked) {
      setStatus('failed');
      return;
    }
    await connectToInternet();
  };

  const getStatusColor = () => {
    if (connected) return 'text-emerald-400';
    if (connecting) return 'text-yellow-400';
    return 'text-gray-400';
  };

  const getConnectionIcon = (type) => {
    switch(type) {
      case 'tor': return <Lock className="w-4 h-4" />;
      case 'proxy': return <Globe className="w-4 h-4" />;
      case 'vpn': return <Lock className="w-4 h-4" />;
      case 'satellite': return <Satellite className="w-4 h-4" />;
      case 'mesh': return <Network className="w-4 h-4" />;
      default: return <Wifi className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute w-96 h-96 -top-48 -left-48 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute w-96 h-96 -bottom-48 -right-48 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute w-96 h-96 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      <div className="relative z-10">
        {/* Header */}
        <header className="p-6 border-b border-white/10 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap className={`w-8 h-8 ${getStatusColor()} transition-colors duration-300`} />
              <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                Manifested Connection
              </h1>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Activity className={`w-5 h-5 ${connected ? 'text-emerald-400 animate-pulse' : 'text-gray-500'}`} />
                <span className="text-sm">{connected ? 'ONLINE' : 'OFFLINE'}</span>
              </div>
              {stats.active > 0 && (
                <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/20 rounded-full">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
                  <span className="text-xs font-medium">{stats.active} Active</span>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto p-6">
          {/* Magic Button Section */}
          <div className="text-center py-16">
            <h2 className="text-5xl font-bold mb-4">
              Free Internet Access
            </h2>
            <p className="text-xl text-purple-300 mb-12">
              Connect to the internet through decentralized networks, proxies, and alternative sources
            </p>

            <button
              onClick={handleConnectClicked}
              disabled={connecting}
              data-testid="connect-button"
              className={`
                relative px-16 py-6 text-2xl font-bold rounded-2xl
                transform transition-all duration-300 hover:scale-105
                ${
                  connecting
                    ? 'bg-yellow-500 cursor-wait animate-pulse'
                    : connected
                    ? 'bg-emerald-500 hover:bg-emerald-600'
                    : 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600'
                }
                shadow-2xl hover:shadow-purple-500/50
                disabled:opacity-75
              `}
            >
              {connecting ? (
                <span className="flex items-center gap-3">
                  <div className="w-6 h-6 border-4 border-white border-t-transparent rounded-full animate-spin"></div>
                  CONNECTING...
                </span>
              ) : connected ? (
                <span className="flex items-center gap-3">
                  <Wifi className="w-8 h-8" />
                  CONNECTED!
                </span>
              ) : (
                <span className="flex items-center gap-3">
                  <Zap className="w-8 h-8" />
                  GET INTERNET NOW
                </span>
              )}
            </button>

            {/* Status Message */}
            {status && status !== 'idle' && (
              <div className="mt-8 text-lg" data-testid="status-message">
                {status === 'discovering' && '🔍 Scanning for connections...'}
                {status === 'discovered' && `✨ Found ${discoveredCount} sources!`}
                {status === 'connecting' && '⚡ Establishing connection...'}
                {status === 'connected' && '🎉 You are now online!'}
                {status === 'failed' && '❌ Connection failed. Trying again...'}
                {status === 'loading' && '📡 Loading webpage...'}
              </div>
            )}
          </div>

          {/* Active Connection Info */}
          {activeConnection && (
            <div className="mb-8 p-6 bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10" data-testid="active-connection">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-400" />
                Active Connection
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-gray-400">Type</div>
                  <div className="text-lg font-semibold flex items-center gap-2 mt-1">
                    {getConnectionIcon(activeConnection.type)}
                    {activeConnection.type.toUpperCase()}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-400">Anonymity</div>
                  <div className="text-lg font-semibold mt-1">
                    {'🔒'.repeat(activeConnection.anonymity_level)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-400">Status</div>
                  <div className="text-lg font-semibold text-emerald-400 mt-1">
                    {activeConnection.status.toUpperCase()}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-400">Latency</div>
                  <div className="text-lg font-semibold mt-1">
                    {activeConnection.latency ? `${Math.round(activeConnection.latency)}ms` : 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Built-in Browser */}
          {connected && (
            <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-6" data-testid="browser-section">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Globe className="w-5 h-5 text-blue-400" />
                Secure Browser
              </h3>
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={browserUrl}
                  onChange={(e) => setBrowserUrl(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && loadWebpage()}
                  placeholder="Enter URL (e.g., https://example.com)"
                  data-testid="url-input"
                  className="flex-1 px-4 py-3 bg-white/10 border border-white/20 rounded-lg focus:outline-none focus:border-purple-400 transition-colors"
                />
                <button
                  onClick={loadWebpage}
                  data-testid="load-button"
                  className="px-6 py-3 bg-purple-500 hover:bg-purple-600 rounded-lg font-semibold transition-colors"
                >
                  GO
                </button>
              </div>

              {showBrowser && (
                <div className="bg-white rounded-lg p-0 text-black max-h-96 overflow-hidden" data-testid="browser-content">
                  <iframe
                    title="preview"
                    sandbox="allow-same-origin allow-forms allow-scripts"
                    srcDoc={browserContent}
                    className="w-full h-96 rounded-lg bg-white"
                  />
                </div>
              )}
            </div>
          )}

          {/* Connection Sources Grid */}
          {connections.length > 0 && (
            <div className="mt-8">
              <h3 className="text-xl font-semibold mb-4">Available Sources ({connections.length})</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="connections-grid">
                {connections.slice(0, 12).map((conn) => (
                  <div
                    key={conn.id}
                    className="p-4 bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 hover:border-purple-400/50 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {getConnectionIcon(conn.type)}
                        <span className="font-semibold">{conn.type.toUpperCase()}</span>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded ${
                        conn.status === 'active' ? 'bg-emerald-500/20 text-emerald-400' :
                        conn.status === 'available' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {conn.status}
                      </span>
                    </div>
                    <div className="text-sm text-gray-400">
                      {'🔒'.repeat(conn.anonymity_level)} Privacy Level
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="text-center py-8 text-gray-400 text-sm">
          <p>⚡ Powered by decentralized networks, proxies, and open internet infrastructure</p>
        </footer>
      </div>
    </div>
  );
}

export default App;
