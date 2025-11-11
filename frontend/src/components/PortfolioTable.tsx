import React, { useState, useEffect } from 'react';

interface Position {
    symbol: string;
    quantity: number;
    avg_price: number;
    last_price: number;
    pnl_pct: number;
}

const PortfolioTable = () => {
    const [positions, setPositions] = useState<Position[]>([]);

    const fetchPositions = async () => {
        try {
            const response = await fetch('/api/dashboard/positions');
            const data: Position[] = await response.json();
            setPositions(data);
        } catch (error) {
            console.error("Failed to fetch positions:", error);
        }
    };

    useEffect(() => {
        fetchPositions();
        const interval = setInterval(fetchPositions, 5000); // Poll every 5 seconds
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-4">Open Positions</h2>
            <div className="overflow-x-auto">
                <table className="min-w-full">
                    <thead>
                        <tr className="border-b border-gray-700">
                            <th className="text-left p-2">Symbol</th>
                            <th className="text-right p-2">Qty</th>
                            <th className="text-right p-2">Avg. Price</th>
                            <th className="text-right p-2">Last Price</th>
                            <th className="text-right p-2">P&L %</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions.length > 0 ? (
                            positions.map(pos => (
                                <tr key={pos.symbol} className="border-b border-gray-700">
                                    <td className="p-2">{pos.symbol}</td>
                                    <td className="text-right p-2">{pos.quantity}</td>
                                    <td className="text-right p-2">{pos.avg_price.toFixed(2)}</td>
                                    <td className="text-right p-2">{pos.last_price.toFixed(2)}</td>
                                    <td className={`text-right p-2 ${pos.pnl_pct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                        {pos.pnl_pct.toFixed(2)}%
                                    </td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan={5} className="text-center p-4 text-gray-500">No open positions.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default PortfolioTable;
