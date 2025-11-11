import React, { useState, useEffect } from 'react';

interface Trade {
    symbol: string;
    exit_ts: string;
    quantity: number;
    exit_price: number;
    side: string; // This is an inferred representation
}

const TradeTape = () => {
    const [trades, setTrades] = useState<Trade[]>([]);

    const fetchTrades = async () => {
        try {
            const response = await fetch('/api/dashboard/trades');
            const data: Trade[] = await response.json();
            setTrades(data);
        } catch (error) {
            console.error("Failed to fetch trades:", error);
        }
    };

    useEffect(() => {
        fetchTrades();
        const interval = setInterval(fetchTrades, 10000); // Poll every 10 seconds
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow">
            <h2 className="text-lg font-semibold mb-4">Today's Trades</h2>
            <div className="overflow-x-auto">
                <table className="min-w-full">
                    <thead>
                        <tr className="border-b border-gray-700 text-sm">
                           <th className="text-left p-2">Time</th>
                           <th className="text-left p-2">Symbol</th>
                           <th className="text-left p-2">Side</th>
                           <th className="text-right p-2">Qty</th>
                           <th className="text-right p-2">Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trades.length > 0 ? (
                            trades.map((trade, i) => (
                                <tr key={i} className="border-b border-gray-700 text-sm">
                                    <td className="p-2">{new Date(trade.exit_ts).toLocaleTimeString('en-IN')}</td>
                                    <td className="p-2">{trade.symbol}</td>
                                    <td className={`p-2 font-semibold ${trade.side === 'BUY' ? 'text-green-500' : 'text-red-500'}`}>{trade.side}</td>
                                    <td className="text-right p-2">{trade.quantity}</td>
                                    <td className="text-right p-2">{trade.exit_price.toFixed(2)}</td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                               <td colSpan={5} className="text-center p-4 text-gray-500">No trades today.</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default TradeTape;
