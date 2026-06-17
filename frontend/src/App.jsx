import { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, Store, Calendar, Activity } from 'lucide-react';

const API_URL = 'http://localhost:8000';

function App() {
  const [meta, setMeta] = useState({ stores: [], items: [], max_date: '' });
  const [storeMap, setStoreMap] = useState({});
  const [itemMap, setItemMap]   = useState({});
  const [form, setForm] = useState({ store: '', item: '', date: '' });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch metadata on load
    axios.get(`${API_URL}/meta`)
      .then(res => {
        setMeta({
          stores: res.data.stores,
          items: res.data.items,
          max_date: res.data.max_historical_date
        });
        // Build lookup maps id -> name
        const sMap = {}; res.data.stores.forEach(s => { sMap[s.id] = s.name; });
        const iMap = {}; res.data.items.forEach(i  => { iMap[i.id]  = i.name;  });
        setStoreMap(sMap);
        setItemMap(iMap);

        if (res.data.stores.length > 0) {
          const defaultDate = new Date(res.data.max_historical_date);
          defaultDate.setDate(defaultDate.getDate() + 1);
          setForm({
            store: res.data.stores[0].id,
            item: res.data.items[0].id,
            date: defaultDate.toISOString().split('T')[0]
          });
        }
      })
      .catch(err => console.error("Error fetching meta:", err));
  }, []);

  const handleForecast = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_URL}/predict`, {
        store: parseInt(form.store),
        item: parseInt(form.item),
        target_date: form.date
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to fetch forecast");
    } finally {
      setLoading(false);
    }
  };

  // Prepare chart data
  const chartData = result ? [
    ...result.history.map(h => ({ date: h.date, actual: h.sales, forecast: null })),
    { date: result.target_date, actual: null, forecast: result.prediction }
  ] : [];

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <div className="flex items-center gap-2 text-indigo-600">
            <Activity size={28} />
            <h1 className="text-2xl font-bold">SalesForecaster AI</h1>
          </div>
          <div className="text-sm text-slate-500 font-medium">Powered by XGBoost & FastAPI</div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          
          {/* Sidebar / Form */}
          <div className="lg:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-slate-100 h-fit">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Store size={20} className="text-slate-500"/>
              Configuration
            </h2>
            <form onSubmit={handleForecast} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Store ID</label>
                <select 
                  className="w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border bg-slate-50"
                  value={form.store}
                  onChange={e => setForm({...form, store: e.target.value})}
                  required
                >
                  {meta.stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Item ID</label>
                <select 
                  className="w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border bg-slate-50"
                  value={form.item}
                  onChange={e => setForm({...form, item: e.target.value})}
                  required
                >
                  {meta.items.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1 flex items-center gap-2">
                  <Calendar size={16}/> Target Date
                </label>
                <input 
                  type="date"
                  className="w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border bg-slate-50"
                  value={form.date}
                  onChange={e => setForm({...form, date: e.target.value})}
                  required
                />
              </div>

              <button 
                type="submit" 
                disabled={loading}
                className="w-full bg-indigo-600 text-white font-medium py-3 rounded-lg hover:bg-indigo-700 transition flex justify-center items-center gap-2 mt-4 shadow-sm"
              >
                {loading ? 'Processing ML...' : '🚀 Get Forecast'}
              </button>
            </form>
          </div>

          {/* Main Dashboard Area */}
          <div className="lg:col-span-3 space-y-6">
            
            {error && (
              <div className="bg-red-50 text-red-700 p-4 rounded-lg border border-red-200">
                {error}
              </div>
            )}

            {!result && !loading && !error && (
              <div className="bg-white border border-dashed border-slate-300 rounded-xl p-12 text-center flex flex-col items-center justify-center text-slate-500">
                <Activity size={48} className="mb-4 text-slate-300"/>
                <h3 className="text-xl font-medium mb-2">Ready to Forecast</h3>
                <p>Select a store, item, and future date on the left to generate an AI-powered prediction.</p>
              </div>
            )}

            {loading && (
              <div className="bg-white rounded-xl p-12 text-center border border-slate-100 shadow-sm">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                <p className="text-slate-500 font-medium">Running XGBoost Model...</p>
              </div>
            )}

            {result && !loading && (
              <>
                {/* KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-white p-6 rounded-xl border border-slate-100 shadow-sm">
                    <p className="text-sm font-medium text-slate-500 mb-1">Predicted Sales</p>
                    <div className="flex items-end gap-2">
                      <h3 className="text-4xl font-black text-slate-800">{result.prediction}</h3>
                      <span className="text-slate-500 mb-1">Units</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-2">For {result.target_date}</p>
                  </div>

                  <div className="bg-white p-6 rounded-xl border border-slate-100 shadow-sm">
                    <p className="text-sm font-medium text-slate-500 mb-1">vs. 7-Day Average</p>
                    <div className="flex items-center gap-3">
                      <div className={`p-3 rounded-full ${result.prediction >= result.last_rolling_7 ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'}`}>
                        {result.prediction >= result.last_rolling_7 ? <TrendingUp size={24}/> : <TrendingDown size={24}/>}
                      </div>
                      <div>
                        <h3 className="text-2xl font-bold text-slate-800">
                          {Math.abs(result.prediction - result.last_rolling_7)}
                        </h3>
                        <p className="text-xs text-slate-500">Diff from Avg ({result.last_rolling_7})</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white p-6 rounded-xl border border-slate-100 shadow-sm flex flex-col justify-center">
                    <p className="text-sm font-medium text-slate-500 mb-1">Target Profile</p>
                    <h3 className="text-xl font-bold text-slate-800">{storeMap[result.store] || `Store ${result.store}`}</h3>
                    <p className="text-md text-slate-600">{itemMap[result.item] || `Item ${result.item}`}</p>
                  </div>
                </div>

                {/* Chart */}
                <div className="bg-white p-6 rounded-xl border border-slate-100 shadow-sm">
                  <h3 className="text-lg font-bold text-slate-800 mb-6">Sales History & AI Forecast</h3>
                  <div className="h-80 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0"/>
                        <XAxis 
                          dataKey="date" 
                          tick={{fill: '#64748b', fontSize: 12}}
                          axisLine={false}
                          tickLine={false}
                          minTickGap={30}
                        />
                        <YAxis 
                          tick={{fill: '#64748b', fontSize: 12}}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip 
                          contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                        />
                        <Legend wrapperStyle={{paddingTop: '20px'}}/>
                        <Line 
                          type="monotone" 
                          dataKey="actual" 
                          name="Historical Sales" 
                          stroke="#3b82f6" 
                          strokeWidth={2}
                          dot={false}
                          activeDot={{r: 6}}
                        />
                        <Line 
                          type="monotone" 
                          dataKey="forecast" 
                          name="AI Prediction" 
                          stroke="#10b981" 
                          strokeWidth={3}
                          strokeDasharray="5 5"
                          dot={{r: 6, fill: '#10b981', strokeWidth: 2, stroke: '#fff'}}
                          activeDot={{r: 8}}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
