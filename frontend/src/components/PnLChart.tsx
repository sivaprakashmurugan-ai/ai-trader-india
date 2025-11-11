import React, { useState, useEffect } from 'react';

interface PnLSnapshot {
    ts: string;
    realized_pnl: number;
    unrealized_pnl: number;
}

const PnLChart = () => {
    const [pnlData, setPnlData] = useState<PnLSnapshot[]>([]);

    const fetchPnlData = async () => {
        try {
            const response = await fetch('/api/dashboard/pnl_timeseries');
            const data: PnLSnapshot[] = await response.json();
            setPnlData(data);
        } catch (error) {
            console.error("Failed to fetch PnL timeseries:", error);
        }
    };

    useEffect(() => {
        fetchPnlData();
        const interval = setInterval(fetchPnlData, 10000); // Poll every 10 seconds
        return () => clearInterval(interval);
    }, []);

    // TODO: Implement a real charting library using the 'pnlData' state
    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow h-full">
            <h2 className="text-lg font-semibold mb-4">PnL Timeseries</h2>
            <div className="flex items-center justify-center h-64 border-2 border-dashed border-gray-600 rounded-lg">
                <p className="text-gray-500">
                    {pnlData.length > 0 ? `Loaded ${pnlData.length} data points.` : 'Waiting for PnL data...'}
                </p>
            </div>
        </div>
    );
};

export default PnLChart;
