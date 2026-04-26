import { useNavigate } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

const CandidateTable = ({ candidates, clickable = false }) => {
  const navigate = useNavigate()

  return (
    <div className="glass overflow-x-auto rounded-2xl">
      <table className="min-w-full text-left text-sm text-indigo-100">
        <thead className="bg-white/10 text-indigo-100/90">
          <tr>
            <th className="px-4 py-2.5 font-semibold">Name</th>
            <th className="px-4 py-2.5 font-semibold">Score</th>
            <th className="px-4 py-2.5 font-semibold">Rank</th>
            {clickable ? <th className="w-12" /> : null}
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr
              key={candidate.id}
              onClick={() =>
                clickable && navigate(`/candidate-analysis/${candidate.id}`)
              }
              className={`group border-t border-white/10 transition ${
                clickable ? 'cursor-pointer hover:bg-white/10' : 'hover:bg-white/5'
              }`}
            >
              <td className="px-4 py-2.5 font-semibold text-white">
                {candidate.name}
              </td>
              <td className="px-4 py-2.5">{candidate.score}%</td>
              <td className="px-4 py-2.5">{candidate.rank}</td>
              {clickable ? (
                <td className="px-3 py-2.5 text-indigo-200/70">
                  <ChevronRight size={16} className="ml-auto transition group-hover:text-cyan-200" />
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default CandidateTable
