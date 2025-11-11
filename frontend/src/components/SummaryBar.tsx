import React, { useState, useEffect } from 'react';

interface DashboardSummary {
    daily_realized_pnl: number;
    unrealized_pnl: number;
    exposure: number;
    trade_count: number;
}

const StatCard = ({ title, value, colorClass = 'text-white' }: { title: string, value: string | number, colorClass?: string }) => (
    <div className="bg-gray-800 p-4 rounded-lg shadow">
        <h3 className="text-sm font-medium text-gray-400">{title}</h3>
        <p className={`text-2xl font-semibold ${colorClass}`}>{value}</p>
    </div>
);

const SummaryBar = () => {
    const [summary, setSummary] = useState<DashboardSummary | null>(null);

    const fetchSummary = async () => {
        try {
            const response = await fetch('/api/dashboard/summary');
            const data: DashboardSummary = await response.json();
            setSummary(data);
        } catch (error) {
            console.error("Failed to fetch summary:", error);
        }
    };

    useEffect(() => {
        fetchSummary();
        const interval = setInterval(fetchSummary, 5000); // Poll every 5 seconds
        return () => clearInterval(interval);
    }, []);

    const totalPnl = (summary?.daily_realized_pnl || 0) + (summary?.unrealized_pnl || 0);
    const pnlColor = totalPnl >= 0 ? 'text-green-500' : 'text-red-500';

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="Today's PnL (Total)" value={summary ? `₹${totalPnl.toFixed(2)}` : 'Loading...'} colorClass={pnlColor} />
            <StatCard title="Total Trades" value={summary ? summary.trade_count : 'Loading...'} />
            <StatCard title="Win Rate" value={"N/A"} />
            <StatCard title="Current Exposure" value={summary ? `₹${summary.exposure.toLocaleString('en-IN')}` : 'Loading...'} />
        </div>
    );
};

export default SummaryBar;
