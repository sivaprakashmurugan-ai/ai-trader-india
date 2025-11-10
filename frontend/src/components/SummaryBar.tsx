import React from 'react';

const StatCard = ({ title, value, colorClass = 'text-white' }: { title: string, value: string | number, colorClass?: string }) => (
    <div className="bg-gray-800 p-4 rounded-lg shadow">
        <h3 className="text-sm font-medium text-gray-400">{title}</h3>
        <p className={`text-2xl font-semibold ${colorClass}`}>{value}</p>
    </div>
);

const SummaryBar = () => {
    // TODO: Replace with data from API
    const summary = {
        pnl: 120.15,
        trades: 12,
        winRate: "66.7%",
        exposure: "₹25,123.50"
    };
    const pnlColor = summary.pnl >= 0 ? 'text-green-500' : 'text-red-500';

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard title="Today's PnL (Net)" value={`₹${summary.pnl.toFixed(2)}`} colorClass={pnlColor} />
            <StatCard title="Total Trades" value={summary.trades} />
            <StatCard title="Win Rate" value={summary.winRate} />
            <StatCard title="Current Exposure" value={summary.exposure} />
        </div>
    );
};

export default SummaryBar;