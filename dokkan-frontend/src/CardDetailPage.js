import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader, AlertCircle, Play } from 'lucide-react';

const API_BASE_URL = 'http://127.0.0.1:5000/api';

const proxyImage = (url) => {
  if (!url) return null;
  return `${API_BASE_URL}/proxy-image?url=${encodeURIComponent(url)}`;
};

// Transformation row component - displays individual transformation state
const TransformationRow = ({ transformation, isBase = false, typeColor, onClick }) => {
  const thumbImage = transformation.assets?.cutin || transformation.assets?.character;
  
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '180px 1fr',
      gap: '1.5rem',
      padding: '1.5rem',
      borderBottom: '1px solid rgba(75, 85, 99, 0.5)',
      alignItems: 'start'
    }}>
      {/* Left: Card thumbnail */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
        <div style={{
          position: 'relative',
          width: '140px',
          height: '160px',
          borderRadius: '0.5rem',
          overflow: 'hidden',
          background: 'rgba(0, 0, 0, 0.3)',
          border: `2px solid ${typeColor.border}`,
          cursor: 'pointer',
          transition: 'transform 0.2s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
        onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
        onClick={onClick}
        >
          {/* Background */}
          {transformation.assets?.background && (
            <img
              src={proxyImage(transformation.assets.background)}
              alt="bg"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                opacity: 0.2,
                filter: 'blur(3px)',
                zIndex: 1
              }}
              onError={(e) => e.target.style.display = 'none'}
            />
          )}

          {/* Character image */}
          {thumbImage && (
            <img
              src={proxyImage(thumbImage)}
              alt={transformation.name}
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                zIndex: 2
              }}
              onError={(e) => e.target.style.display = 'none'}
            />
          )}

          {/* Rarity icon */}
          {transformation.assets?.rarity && (
            <img
              src={proxyImage(transformation.assets.rarity)}
              alt={transformation.rarity}
              style={{
                position: 'absolute',
                top: '0.25rem',
                left: '0.25rem',
                width: '2rem',
                height: '2rem',
                zIndex: 3
              }}
              onError={(e) => e.target.style.display = 'none'}
            />
          )}
        </div>

        {/* Label under card */}
        <p style={{
          fontSize: '0.75rem',
          fontWeight: 'bold',
          color: '#fbbf24',
          margin: 0,
          textAlign: 'center',
          textTransform: 'uppercase'
        }}>
          {isBase ? 'Base' : 'Transformation'}
        </p>
      </div>

      {/* Right: Details */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Name and type */}
        <div>
          <h3 style={{
            fontSize: '1.125rem',
            fontWeight: 'bold',
            color: 'white',
            margin: '0 0 0.5rem 0'
          }}>
            {transformation.name}
          </h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{
              padding: '0.25rem 0.75rem',
              borderRadius: '0.375rem',
              fontSize: '0.8rem',
              fontWeight: 'bold',
              background: typeColor.contentBg,
              border: `1px solid ${typeColor.border}`,
              color: typeColor.border
            }}>
              {transformation.rarity}
            </span>
            <span style={{
              padding: '0.25rem 0.75rem',
              borderRadius: '0.375rem',
              fontSize: '0.8rem',
              fontWeight: 'bold',
              background: typeColor.contentBg,
              border: `1px solid ${typeColor.border}`,
              color: typeColor.border
            }}>
              [{transformation.type}]
            </span>
            <span style={{
              fontSize: '0.8rem',
              color: '#9ca3af'
            }}>
              ID: {transformation.id}
            </span>
          </div>
        </div>

        {/* Transformation conditions if available */}
        {transformation.transformationConditions && (
          <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '0.5rem', padding: '1rem', border: '1px solid rgba(75, 85, 99, 0.5)' }}>
            <p style={{ fontSize: '0.875rem', color: '#fbbf24', fontWeight: 'bold', margin: '0 0 0.5rem 0' }}>
              Transformation Condition(s)
            </p>
            <p style={{ fontSize: '0.875rem', color: '#e5e7eb', margin: 0, lineHeight: 1.5 }}>
              {transformation.transformationConditions}
            </p>
          </div>
        )}

        {/* Reversal conditions if available */}
        {transformation.reversalConditions && (
          <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '0.5rem', padding: '1rem', border: '1px solid rgba(75, 85, 99, 0.5)' }}>
            <p style={{ fontSize: '0.875rem', color: '#fbbf24', fontWeight: 'bold', margin: '0 0 0.5rem 0' }}>
              Reversal Condition
            </p>
            <p style={{ fontSize: '0.875rem', color: '#e5e7eb', margin: 0, lineHeight: 1.5 }}>
              {transformation.reversalConditions}
            </p>
          </div>
        )}

        {/* Animation buttons if available */}
        {(transformation.animations || []).length > 0 && (
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {transformation.animations.map((anim, idx) => (
              <button
                key={idx}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 1rem',
                  borderRadius: '0.5rem',
                  border: `2px solid ${typeColor.border}`,
                  background: 'rgba(0,0,0,0.3)',
                  color: typeColor.border,
                  fontWeight: 'bold',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = typeColor.contentBg}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(0,0,0,0.3)'}
              >
                <Play className="w-3 h-3" />
                {anim}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default function CardDetailPage() {
  const { cardId } = useParams();
  const navigate = useNavigate();
  const [card, setCard] = useState(null);
  const [allCards, setAllCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchCardDetails();
    fetchAllCards();
  }, [cardId]);

  const fetchCardDetails = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE_URL}/cards/${cardId}`);
      const data = await response.json();

      if (data.success) {
        setCard(data.card);
      } else {
        setError(data.error || 'Card not found');
      }
    } catch (err) {
      setError(`Failed to load card: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchAllCards = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/cards`);
      const data = await response.json();
      if (data.success) {
        setAllCards(data.cards);
      }
    } catch (err) {
      console.error('Failed to fetch all cards:', err);
    }
  };

  const findAllVersions = () => {
    if (!card || !allCards.length) return [];

    const baseName = card.name.replace(/\[.*?\]/g, '').trim();

    // Find all cards with the same base name
    const allVersions = allCards.filter(c => {
      const cName = c.name.replace(/\[.*?\]/g, '').trim();
      return baseName === cName;
    });

    // Sort by rarity (highest first), then by ID
    const rarityOrder = { 'LR': 5, 'UR': 4, 'SSR': 3, 'SR': 2, 'R': 1, 'N': 0 };
    
    return allVersions.sort((a, b) => {
      const rarityDiff = rarityOrder[b.rarity] - rarityOrder[a.rarity];
      if (rarityDiff !== 0) return rarityDiff;
      return parseInt(b.id) - parseInt(a.id);
    });
  };

  const typeColors = {
    STR: {
      gradient: 'linear-gradient(135deg, #b91c1c 0%, #7f1d1d 100%)',
      border: '#ef4444',
      headerBg: '#7f1d1d',
      contentBg: 'rgba(127, 29, 29, 0.2)'
    },
    TEQ: {
      gradient: 'linear-gradient(135deg, #d97706 0%, #92400e 100%)',
      border: '#f59e0b',
      headerBg: '#92400e',
      contentBg: 'rgba(146, 64, 14, 0.2)'
    },
    INT: {
      gradient: 'linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%)',
      border: '#a78bfa',
      headerBg: '#5b21b6',
      contentBg: 'rgba(91, 33, 182, 0.2)'
    },
    AGL: {
      gradient: 'linear-gradient(135deg, #2563eb 0%, #1e3a8a 100%)',
      border: '#3b82f6',
      headerBg: '#1e3a8a',
      contentBg: 'rgba(30, 58, 138, 0.2)'
    },
    PHY: {
      gradient: 'linear-gradient(135deg, #16a34a 0%, #14532d 100%)',
      border: '#22c55e',
      headerBg: '#14532d',
      contentBg: 'rgba(21, 83, 45, 0.2)'
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #111827 0%, #1f2937 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader className="w-12 h-12 text-yellow-500 animate-spin" />
      </div>
    );
  }

  if (error || !card) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #111827 0%, #1f2937 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <p style={{ color: '#f87171', fontSize: '1.25rem', marginBottom: '1rem' }}>{error || 'Card not found'}</p>
          <button
            onClick={() => navigate('/')}
            style={{ padding: '0.5rem 1.5rem', background: '#ca8a04', color: 'white', borderRadius: '0.5rem', border: 'none', cursor: 'pointer' }}
          >
            Back to Cards
          </button>
        </div>
      </div>
    );
  }

  const typeColor = typeColors[card.type] || typeColors.INT;
  const thumbImage = card.assets?.cutin || card.assets?.character;
  const allVersions = findAllVersions();

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #111827 0%, #1f2937 100%)' }}>
      {/* Header */}
      <header style={{ background: 'rgba(17, 24, 39, 0.95)', borderBottom: '1px solid rgba(75, 85, 99, 0.5)', position: 'sticky', top: 0, zIndex: 50, backdropFilter: 'blur(12px)' }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '1rem 2rem' }}>
          <button
            onClick={() => navigate('/')}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#9ca3af', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '1rem' }}
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Cards</span>
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '2rem' }}>

          {/* Left Sidebar */}
          <div>
            {/* Card Image */}
            <div style={{
              position: 'relative',
              background: typeColor.gradient,
              borderRadius: '1rem',
              padding: '4px',
              boxShadow: `0 0 30px ${typeColor.border}40`,
              marginBottom: '1.5rem'
            }}>
              <div style={{
                position: 'relative',
                background: '#1f2937',
                borderRadius: '0.875rem',
                overflow: 'hidden',
                height: '480px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                {/* Background Base */}
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  background: typeColor.gradient,
                  opacity: 0.3,
                  zIndex: 0
                }} />

                {/* Character Image */}
                {thumbImage && (
                  <img
                    src={proxyImage(thumbImage)}
                    alt={card.name}
                    style={{
                      position: 'relative',
                      maxWidth: '90%',
                      maxHeight: '90%',
                      objectFit: 'contain',
                      zIndex: 2
                    }}
                  />
                )}

                {/* Top Icons */}
                <div style={{ position: 'absolute', top: '1rem', left: '1rem', display: 'flex', gap: '0.5rem', zIndex: 10 }}>
                  {card.assets?.rarity && (
                    <img src={proxyImage(card.assets.rarity)} alt={card.rarity} style={{ width: '3rem', height: '3rem', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.8))' }} onError={(e) => e.target.style.display = 'none'} />
                  )}
                  {card.assets?.type && (
                    <img src={proxyImage(card.assets.type)} alt={card.type} style={{ width: '3rem', height: '3rem', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.8))' }} onError={(e) => e.target.style.display = 'none'} />
                  )}
                </div>

                {/* EZA Badge */}
                {card.eza?.hasEza && (
                  <div style={{
                    position: 'absolute',
                    top: '1rem',
                    right: '1rem',
                    padding: '0.5rem 1rem',
                    borderRadius: '0.5rem',
                    background: card.eza.isSeza ? 'linear-gradient(135deg, #9333ea, #db2777)' : 'linear-gradient(135deg, #d97706, #ea580c)',
                    color: 'white',
                    fontSize: '0.875rem',
                    fontWeight: 'bold',
                    zIndex: 10,
                    boxShadow: '0 4px 6px rgba(0,0,0,0.5)'
                  }}>
                    {card.eza.isSeza ? 'SEZA' : 'EZA'}
                  </div>
                )}
              </div>
            </div>

            {/* Card Title */}
            <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
              <h1 style={{ fontSize: '1.3rem', fontWeight: 'bold', color: 'white', lineHeight: 1.2, marginBottom: '0.5rem' }}>
                {card.name}
              </h1>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                <span style={{
                  padding: '0.25rem 0.75rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  fontWeight: 'bold',
                  background: typeColor.contentBg,
                  border: `2px solid ${typeColor.border}`,
                  color: typeColor.border
                }}>
                  {card.rarity}
                </span>
                <span style={{
                  padding: '0.25rem 0.75rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  fontWeight: 'bold',
                  background: typeColor.contentBg,
                  border: `2px solid ${typeColor.border}`,
                  color: typeColor.border
                }}>
                  [{card.type}]
                </span>
              </div>
              <p style={{ color: '#9ca3af', fontSize: '0.85rem', margin: '0.5rem 0 0 0' }}>ID: {card.id}</p>
              {card.releaseDate && (
                <p style={{ color: '#6b7280', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                  Released: {card.releaseDate}
                </p>
              )}
            </div>
          </div>

          {/* Right Content Area */}
          <div>
            {/* Tabs */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
              {['overview', 'stats', 'links'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '0.75rem 1.5rem',
                    borderRadius: '0.5rem',
                    fontWeight: 'bold',
                    textTransform: 'capitalize',
                    transition: 'all 0.2s',
                    border: 'none',
                    cursor: 'pointer',
                    background: activeTab === tab ? typeColor.gradient : '#374151',
                    color: 'white',
                    boxShadow: activeTab === tab ? `0 4px 12px ${typeColor.border}40` : 'none'
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {activeTab === 'overview' && (
                <>
                  {/* Transformations/Versions Section */}
                  {allVersions.length > 1 && (
                    <div style={{ border: `3px solid ${typeColor.border}`, borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: typeColor.headerBg, padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>
                          Transformations / Exchanges
                        </h2>
                      </div>
                      <div style={{ background: typeColor.contentBg, backdropFilter: 'blur(10px)' }}>
                        {allVersions.map((version, idx) => (
                          <TransformationRow
                            key={version.id}
                            transformation={version}
                            isBase={idx === 0}
                            typeColor={typeColor}
                            onClick={() => navigate(`/card/${version.id}`)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {card.leaderSkill && (
                    <div style={{ border: `3px solid ${typeColor.border}`, borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: typeColor.headerBg, padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>Leader Skill</h2>
                      </div>
                      <div style={{ background: typeColor.contentBg, padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <p style={{ color: '#e5e7eb', lineHeight: 1.6, margin: 0 }}>{card.leaderSkill}</p>
                      </div>
                    </div>
                  )}

                  {card.passiveSkill?.name && (
                    <div style={{ border: `3px solid ${typeColor.border}`, borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: typeColor.headerBg, padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>
                          Passive Skill | <span style={{ color: '#fcd34d' }}>{card.passiveSkill.name}</span>
                        </h2>
                      </div>
                      <div style={{ background: typeColor.contentBg, padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        {card.passiveSkill.structured && card.passiveSkill.structured.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            {card.passiveSkill.structured.map((section, idx) => (
                              <div key={idx}>
                                <p style={{ fontWeight: 'bold', color: '#fbbf24', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                                  {section.condition}
                                </p>
                                <ul style={{ listStyle: 'disc', paddingLeft: '1.5rem', margin: 0 }}>
                                  {section.effects.map((effect, effIdx) => (
                                    <li key={effIdx} style={{ color: '#e5e7eb', fontSize: '0.875rem', lineHeight: 1.6, marginBottom: '0.25rem' }}>
                                      {effect}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p style={{ color: '#e5e7eb', margin: 0 }}>{card.passiveSkill.text}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {card.superAttack?.name && (
                    <div style={{ border: '3px solid #22c55e', borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: 'linear-gradient(135deg, #16a34a, #14532d)', padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>
                          Super Attack (12 Ki) | <span style={{ color: '#fcd34d' }}>{card.superAttack.name}</span>
                        </h2>
                      </div>
                      <div style={{ background: 'rgba(21, 83, 45, 0.2)', padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <p style={{ color: '#e5e7eb', lineHeight: 1.6, margin: 0 }}>{card.superAttack.effect}</p>
                      </div>
                    </div>
                  )}

                  {card.ultraSuperAttack?.name && (
                    <div style={{ border: '3px solid #a78bfa', borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: 'linear-gradient(135deg, #7c3aed, #5b21b6)', padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>
                          Ultra Super Attack (18 Ki) | <span style={{ color: '#fcd34d' }}>{card.ultraSuperAttack.name}</span>
                        </h2>
                      </div>
                      <div style={{ background: 'rgba(91, 33, 182, 0.2)', padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <p style={{ color: '#e5e7eb', lineHeight: 1.6, margin: 0 }}>{card.ultraSuperAttack.effect}</p>
                      </div>
                    </div>
                  )}

                  {card.activeSkill?.name && (
                    <div style={{ border: '3px solid #f59e0b', borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: 'linear-gradient(135deg, #d97706, #92400e)', padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>
                          Active Skill | <span style={{ color: '#fcd34d' }}>{card.activeSkill.name}</span>
                        </h2>
                      </div>
                      <div style={{ background: 'rgba(146, 64, 14, 0.2)', padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <p style={{ color: '#e5e7eb', lineHeight: 1.6, marginBottom: card.activeSkill.conditions ? '1rem' : 0 }}>
                          {card.activeSkill.effect}
                        </p>
                        {card.activeSkill.conditions && (
                          <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '0.5rem', padding: '1rem', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                            <p style={{ fontSize: '0.875rem', color: '#d1d5db', margin: 0 }}>
                              <span style={{ fontWeight: 'bold', color: '#fbbf24' }}>Activation Conditions:</span><br/>
                              {card.activeSkill.conditions}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}

              {activeTab === 'stats' && (
                <>
                  {card.stats?.generalInfo && (
                    <div style={{ border: `3px solid ${typeColor.border}`, borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: typeColor.headerBg, padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>General Info</h2>
                      </div>
                      <div style={{ background: typeColor.contentBg, padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                          {Object.entries(card.stats.generalInfo).map(([key, value]) => (
                            <div key={key} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '0.5rem', padding: '1rem', textAlign: 'center', border: '1px solid rgba(75, 85, 99, 0.5)' }}>
                              <p style={{ color: '#9ca3af', fontSize: '0.875rem', marginBottom: '0.25rem' }}>{key}</p>
                              <p style={{ color: 'white', fontSize: '1.5rem', fontWeight: 'bold', margin: 0 }}>{value}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {card.stats?.baseStats && (
                    <div style={{ border: `3px solid ${typeColor.border}`, borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: typeColor.headerBg, padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>Stats</h2>
                      </div>
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                          <thead style={{ background: '#111827' }}>
                            <tr>
                              <th style={{ padding: '1rem 1.5rem', textAlign: 'left', fontSize: '0.875rem', fontWeight: 'bold', color: '#d1d5db' }}>Stat</th>
                              <th style={{ padding: '1rem 1.5rem', textAlign: 'center', fontSize: '0.875rem', fontWeight: 'bold', color: '#d1d5db' }}>Base Min</th>
                              <th style={{ padding: '1rem 1.5rem', textAlign: 'center', fontSize: '0.875rem', fontWeight: 'bold', color: '#d1d5db' }}>Base Max</th>
                              {card.stats.hiddenPotential && Object.keys(card.stats.hiddenPotential).map(percent => (
                                <th key={percent} style={{ padding: '1rem 1.5rem', textAlign: 'center', fontSize: '0.875rem', fontWeight: 'bold', color: '#d1d5db' }}>{percent}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody style={{ background: typeColor.contentBg }}>
                            {['HP', 'ATK', 'DEF'].map((stat, idx) => (
                              <tr key={stat} style={{ borderTop: idx > 0 ? '1px solid rgba(75, 85, 99, 0.5)' : 'none' }}>
                                <td style={{ padding: '1rem 1.5rem', fontWeight: 'bold', fontSize: '1.125rem', color: typeColor.border }}>{stat}</td>
                                <td style={{ padding: '1rem 1.5rem', textAlign: 'center', color: 'white', fontWeight: '600' }}>
                                  {card.stats.baseStats[stat]?.['Base Min']?.toLocaleString() || '-'}
                                </td>
                                <td style={{ padding: '1rem 1.5rem', textAlign: 'center', color: 'white', fontWeight: '600' }}>
                                  {card.stats.baseStats[stat]?.['Base Max']?.toLocaleString() || '-'}
                                </td>
                                {card.stats.hiddenPotential && Object.entries(card.stats.hiddenPotential).map(([percent, values]) => (
                                  <td key={percent} style={{ padding: '1rem 1.5rem', textAlign: 'center', color: 'white', fontWeight: '600' }}>
                                    {values[stat]?.toLocaleString() || '-'}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}

              {activeTab === 'links' && (
                <>
                  {card.linkSkills && card.linkSkills.length > 0 && (
                    <div style={{ border: '3px solid #22c55e', borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: 'linear-gradient(135deg, #16a34a, #14532d)', padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>Link Skills</h2>
                      </div>
                      <div style={{ background: 'rgba(21, 83, 45, 0.2)', padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem' }}>
                          {card.linkSkills.map((link, idx) => (
                            <div key={idx} style={{
                              background: 'rgba(22, 163, 74, 0.2)',
                              border: '2px solid #22c55e',
                              borderRadius: '0.5rem',
                              padding: '1rem',
                              textAlign: 'center'
                            }}>
                              <p style={{ color: '#86efac', fontWeight: 'bold', margin: 0, fontSize: '0.875rem' }}>{link}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {card.categories && card.categories.length > 0 && (
                    <div style={{ border: '3px solid #3b82f6', borderRadius: '0.75rem', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                      <div style={{ background: 'linear-gradient(135deg, #2563eb, #1e3a8a)', padding: '1rem 1.5rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 'bold', color: 'white', margin: 0 }}>Categories</h2>
                      </div>
                      <div style={{ background: 'rgba(30, 58, 138, 0.2)', padding: '1.5rem', backdropFilter: 'blur(10px)' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
                          {card.categories.map((cat, idx) => (
                            <span
                              key={idx}
                              style={{
                                padding: '0.5rem 1rem',
                                background: 'rgba(37, 99, 235, 0.2)',
                                border: '2px solid #3b82f6',
                                borderRadius: '9999px',
                                color: '#93c5fd',
                                fontWeight: 'bold',
                                fontSize: '0.875rem'
                              }}
                            >
                              {cat}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}