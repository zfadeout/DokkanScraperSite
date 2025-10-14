import React, { useState, useEffect } from 'react';
import { Search, Filter, Star, Loader, AlertCircle } from 'lucide-react';
import './App.css';

const API_BASE_URL = 'http://127.0.0.1:5000/api';

// Helper to proxy images through our backend
const proxyImage = (url) => {
  if (!url) return null;
  return `${API_BASE_URL}/proxy-image?url=${encodeURIComponent(url)}`;
};

const CharacterCard = ({ character }) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [loadedImages, setLoadedImages] = useState({
    background: false,
    effect: false,
    character: false
  });

  // Debug: Log assets for cards that aren't loading
  useEffect(() => {
    if (!character.assets?.character) {
      console.log(`Card ${character.name} missing character asset:`, character.assets);
    }
  }, [character]);

  const typeColors = {
    STR: 'from-red-600 to-red-800',
    TEQ: 'from-yellow-500 to-orange-600',
    INT: 'from-purple-600 to-purple-800',
    AGL: 'from-blue-600 to-blue-800',
    PHY: 'from-green-600 to-green-800'
  };

  const rarityColors = {
    LR: 'text-yellow-300',
    UR: 'text-purple-300',
    SSR: 'text-blue-300',
    SR: 'text-green-300'
  };

  return (
    <div 
      className="character-card"
      onClick={() => setShowDetails(!showDetails)}
      style={{
        background: `linear-gradient(135deg, ${typeColors[character.type] || 'rgba(55, 65, 81, 0.8)'}, rgba(31, 41, 55, 0.9))`
      }}
    >
      {/* Card Image Container with Layered Images */}
      <div className="card-image-container">
        {/* Background Image - Layer 1 */}
        {character.assets?.background && (
          <img 
            src={proxyImage(character.assets.background)}
            alt="background"
            className="card-bg-image"
            onLoad={() => setLoadedImages(prev => ({ ...prev, background: true }))}
            onError={(e) => {
              console.log(`Failed to load background for ${character.name}`);
              e.target.style.display = 'none';
            }}
          />
        )}
        
        {/* Effect Image - Layer 2 */}
        {character.assets?.effect && (
          <img 
            src={proxyImage(character.assets.effect)}
            alt="effect"
            className="card-effect-image"
            onLoad={() => setLoadedImages(prev => ({ ...prev, effect: true }))}
            onError={(e) => {
              console.log(`Failed to load effect for ${character.name}`);
              e.target.style.display = 'none';
            }}
          />
        )}
        
        {/* Character Image - Layer 3 (Main) - Try multiple sources */}
        {character.assets?.character ? (
          <img 
            src={proxyImage(character.assets.character)}
            alt={character.name}
            className="card-character-image"
            onLoad={() => {
              setImageLoaded(true);
              setLoadedImages(prev => ({ ...prev, character: true }));
            }}
            onError={(e) => {
              console.log(`Failed to load character for ${character.name}, trying cutin...`);
              // Try cutin as fallback
              if (character.assets?.cutin) {
                e.target.src = proxyImage(character.assets.cutin);
              } else {
                e.target.style.display = 'none';
                setImageLoaded(true);
              }
            }}
          />
        ) : character.assets?.cutin ? (
          // Use cutin if character image doesn't exist
          <img 
            src={proxyImage(character.assets.cutin)}
            alt={character.name}
            className="card-character-image"
            onLoad={() => {
              setImageLoaded(true);
              setLoadedImages(prev => ({ ...prev, character: true }));
            }}
            onError={(e) => {
              console.log(`Failed to load cutin for ${character.name}`);
              e.target.style.display = 'none';
              setImageLoaded(true);
            }}
          />
        ) : null}

        {/* Loading Spinner */}
        {!imageLoaded && (
          <div className="spinner">
            <Loader className="w-8 h-8 text-gray-500 animate-spin" />
          </div>
        )}

        {/* Placeholder if no main image loaded */}
        {imageLoaded && !loadedImages.character && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
            color: 'rgb(156, 163, 175)',
            fontSize: '0.875rem',
            zIndex: 4
          }}>
            <p>Image Unavailable</p>
            <p style={{ fontSize: '0.75rem', marginTop: '4px' }}>ID: {character.id}</p>
          </div>
        )}

        {/* Top Icons */}
        <div className="card-icons">
          {character.assets?.rarity && (
            <img 
              src={proxyImage(character.assets.rarity)}
              alt={character.rarity}
              onError={(e) => {
                console.log(`Failed to load rarity icon for ${character.name}`);
                e.target.style.display = 'none';
              }}
            />
          )}
          {character.assets?.type && (
            <img 
              src={proxyImage(character.assets.type)}
              alt={character.type}
              onError={(e) => {
                console.log(`Failed to load type icon for ${character.name}`);
                e.target.style.display = 'none';
              }}
            />
          )}
        </div>

        {/* EZA Badge */}
        {character.eza?.hasEza && (
          <div 
            className="eza-badge"
            style={{
              background: character.eza.isSeza 
                ? 'linear-gradient(135deg, rgb(147, 51, 234), rgb(219, 39, 119))'
                : 'linear-gradient(135deg, rgb(217, 119, 6), rgb(234, 88, 12))'
            }}
          >
            {character.eza.isSeza ? 'SEZA' : 'EZA'}
          </div>
        )}
      </div>

      {/* Card Info Section */}
      <div className="card-info">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 className="card-name">{character.name}</h3>
            <div className="card-meta">
              <span className={`${rarityColors[character.rarity]} text-sm font-semibold`}>
                {character.rarity}
              </span>
              <span style={{ fontSize: '0.875rem', color: 'rgb(209, 213, 219)' }}>
                [{character.type}]
              </span>
            </div>
          </div>
          <Star className="w-5 h-5 text-yellow-400" style={{ flexShrink: 0 }} />
        </div>

        {/* Expanded Details */}
        {showDetails && (
          <div style={{ 
            marginTop: '12px', 
            paddingTop: '12px', 
            borderTop: '1px solid rgba(75, 85, 99, 0.5)',
            maxHeight: '300px',
            overflowY: 'auto'
          }}>
            {/* Leader Skill */}
            {character.leaderSkill && (
              <div style={{ marginBottom: '12px' }}>
                <p style={{ fontSize: '0.75rem', color: 'rgb(209, 213, 219)' }}>
                  <span style={{ fontWeight: 600, color: 'rgb(250, 204, 21)' }}>Leader: </span>
                  {character.leaderSkill}
                </p>
              </div>
            )}

            {/* Super Attack */}
            {character.superAttack?.name && (
              <div style={{ marginBottom: '8px' }}>
                <p style={{ fontSize: '0.75rem', color: 'rgb(209, 213, 219)' }}>
                  <span style={{ fontWeight: 600, color: 'rgb(34, 197, 94)' }}>Super Attack: </span>
                  {character.superAttack.name}
                </p>
                {character.superAttack.effect && (
                  <p style={{ fontSize: '0.7rem', color: 'rgb(156, 163, 175)', marginTop: '4px' }}>
                    {character.superAttack.effect}
                  </p>
                )}
              </div>
            )}

            {/* Ultra Super Attack */}
            {character.ultraSuperAttack?.name && (
              <div style={{ marginBottom: '8px' }}>
                <p style={{ fontSize: '0.75rem', color: 'rgb(209, 213, 219)' }}>
                  <span style={{ fontWeight: 600, color: 'rgb(168, 85, 247)' }}>Ultra Super: </span>
                  {character.ultraSuperAttack.name}
                </p>
                {character.ultraSuperAttack.effect && (
                  <p style={{ fontSize: '0.7rem', color: 'rgb(156, 163, 175)', marginTop: '4px' }}>
                    {character.ultraSuperAttack.effect}
                  </p>
                )}
              </div>
            )}

            {/* Passive Skill */}
            {character.passiveSkill?.name && (
              <div style={{ marginBottom: '8px' }}>
                <p style={{ fontSize: '0.75rem', color: 'rgb(209, 213, 219)' }}>
                  <span style={{ fontWeight: 600, color: 'rgb(96, 165, 250)' }}>Passive: </span>
                  {character.passiveSkill.name}
                </p>
                {character.passiveSkill.text && (
                  <p style={{ fontSize: '0.7rem', color: 'rgb(156, 163, 175)', marginTop: '4px' }}>
                    {character.passiveSkill.text}
                  </p>
                )}
              </div>
            )}

            {/* Active Skill */}
            {character.activeSkill?.name && (
              <div style={{ marginBottom: '8px' }}>
                <p style={{ fontSize: '0.75rem', color: 'rgb(209, 213, 219)' }}>
                  <span style={{ fontWeight: 600, color: 'rgb(251, 146, 60)' }}>Active: </span>
                  {character.activeSkill.name}
                </p>
                {character.activeSkill.effect && (
                  <p style={{ fontSize: '0.7rem', color: 'rgb(156, 163, 175)', marginTop: '4px' }}>
                    {character.activeSkill.effect}
                  </p>
                )}
              </div>
            )}

            {/* Categories */}
            {character.categories && character.categories.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'rgb(250, 204, 21)', marginBottom: '6px' }}>
                  Categories:
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {character.categories.map((cat, idx) => (
                    <span 
                      key={idx}
                      style={{
                        fontSize: '0.7rem',
                        padding: '4px 8px',
                        background: 'rgba(31, 41, 55, 0.8)',
                        borderRadius: '9999px',
                        color: 'rgb(209, 213, 219)'
                      }}
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Link Skills */}
            {character.linkSkills && character.linkSkills.length > 0 && (
              <div style={{ marginTop: '12px' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'rgb(250, 204, 21)', marginBottom: '6px' }}>
                  Link Skills:
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {character.linkSkills.map((link, idx) => (
                    <span 
                      key={idx}
                      style={{
                        fontSize: '0.7rem',
                        padding: '4px 8px',
                        background: 'rgba(31, 41, 55, 0.8)',
                        borderRadius: '9999px',
                        color: 'rgb(209, 213, 219)'
                      }}
                    >
                      {link}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default function App() {
  const [characters, setCharacters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [filterRarity, setFilterRarity] = useState('ALL');
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchCards();
    fetchStats();
  }, []);

  const fetchCards = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API_BASE_URL}/cards`);
      const data = await response.json();
      
      if (data.success) {
        setCharacters(data.cards);
      } else {
        setError(data.error || 'Failed to load cards');
      }
    } catch (err) {
      setError(`Failed to connect to API: ${err.message}`);
      console.error('Error fetching cards:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`);
      const data = await response.json();
      
      if (data.success) {
        setStats(data.stats);
      }
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const filteredCharacters = characters.filter(char => {
    const matchesSearch = char.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         char.displayNameWithType?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = filterType === 'ALL' || char.type === filterType;
    const matchesRarity = filterRarity === 'ALL' || char.rarity === filterRarity;
    return matchesSearch && matchesType && matchesRarity;
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <header className="bg-gray-900/50 backdrop-blur-md border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl sm:text-4xl font-bold bg-gradient-to-r from-yellow-400 via-orange-500 to-red-500 bg-clip-text text-transparent">
                DOKKAN BATTLE
              </h1>
              <p className="text-sm text-gray-400 mt-1">Character Database</p>
            </div>
            <div className="flex items-center gap-3">
              {loading ? (
                <div className="px-4 py-2 bg-gray-800 rounded-lg">
                  <Loader className="w-5 h-5 text-gray-400 animate-spin" />
                </div>
              ) : (
                <div className="px-4 py-2 bg-gradient-to-r from-yellow-600 to-orange-600 rounded-lg">
                  <span className="text-white font-semibold text-sm">
                    {filteredCharacters.length} Cards
                  </span>
                </div>
              )}
            </div>
          </div>

          {!loading && !error && (
            <div className="mt-6 space-y-4">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="Search characters..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-12 pr-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent"
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <div className="flex items-center gap-2">
                  <Filter className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-400">Type:</span>
                  {['ALL', 'STR', 'TEQ', 'INT', 'AGL', 'PHY'].map(type => (
                    <button
                      key={type}
                      onClick={() => setFilterType(type)}
                      className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        filterType === type
                          ? 'bg-yellow-600 text-white'
                          : 'bg-gray-800/50 text-gray-400 hover:bg-gray-700'
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Rarity:</span>
                  {['ALL', 'LR', 'UR', 'SSR', 'SR'].map(rarity => (
                    <button
                      key={rarity}
                      onClick={() => setFilterRarity(rarity)}
                      className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                        filterRarity === rarity
                          ? 'bg-yellow-600 text-white'
                          : 'bg-gray-800/50 text-gray-400 hover:bg-gray-700'
                      }`}
                    >
                      {rarity}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader className="w-12 h-12 text-yellow-500 animate-spin mb-4" />
            <p className="text-gray-400 text-lg">Loading characters...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20">
            <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
            <p className="text-red-400 text-lg mb-2">Error loading data</p>
            <p className="text-gray-400 text-sm mb-4">{error}</p>
            <button
              onClick={fetchCards}
              className="px-6 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        ) : filteredCharacters.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-400 text-lg">No characters found</p>
            {(searchTerm || filterType !== 'ALL' || filterRarity !== 'ALL') && (
              <button
                onClick={() => {
                  setSearchTerm('');
                  setFilterType('ALL');
                  setFilterRarity('ALL');
                }}
                className="mt-4 px-6 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredCharacters.map((character) => (
              <CharacterCard key={character.id} character={character} />
            ))}
          </div>
        )}
      </main>

      <footer className="bg-gray-900/50 border-t border-gray-800 mt-16 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-4">
            <p className="text-gray-400 text-sm">
              Data sourced from <span className="text-yellow-500">dokkaninfo.com</span>
            </p>
          </div>
          
          {stats && (
            <div className="flex justify-center gap-6 text-sm">
              <div className="text-gray-400">
                Total: <span className="text-white font-semibold">{stats.totalCards}</span>
              </div>
              {stats.byRarity && Object.entries(stats.byRarity).map(([rarity, count]) => (
                <div key={rarity} className="text-gray-400">
                  {rarity}: <span className="text-white font-semibold">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </footer>
    </div>
  );
}