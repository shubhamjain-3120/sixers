import type { BlockDealOut } from '../../types'

export default function BlockDealsTable({ deals }: { deals: BlockDealOut[] }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        Block / Bulk Deals (last 5 days)
      </h2>
      {deals.length === 0 ? (
        <p className="text-gray-600 text-sm">No block or bulk deals found.</p>
      ) : (
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="pb-2 pr-4">Date</th>
              <th className="pb-2 pr-4">Client</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4 text-right">Qty</th>
              <th className="pb-2 pr-4 text-right">Price</th>
              <th className="pb-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d, i) => (
              <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-1.5 pr-4 text-gray-300">{d.deal_date}</td>
                <td className="py-1.5 pr-4 text-gray-200 max-w-[160px] truncate">{d.client_name ?? '–'}</td>
                <td className={`py-1.5 pr-4 font-semibold ${d.deal_type === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                  {d.deal_type ?? '–'}
                </td>
                <td className="py-1.5 pr-4 text-right text-gray-300">
                  {d.quantity != null ? d.quantity.toLocaleString('en-IN') : '–'}
                </td>
                <td className="py-1.5 pr-4 text-right text-gray-300">
                  {d.price != null ? `₹${d.price.toFixed(2)}` : '–'}
                </td>
                <td className="py-1.5 text-gray-500 uppercase">{d.source ?? '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
