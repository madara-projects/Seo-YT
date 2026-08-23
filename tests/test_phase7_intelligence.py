from __future__ import annotations
import os, sqlite3, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from win_engine.analysis.demand_explorer import analyze_demand, idea_fingerprint
from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.core.schemas import CreateWatchChannelRequest, CreateWatchVideoRequest, DemandResearchRequest
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.intelligence_store import IntelligenceStore, duration_seconds
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION, prepare_database
from win_engine.ingestion.youtube_client import YouTubeClient

NOW="2026-08-22T00:00:00+00:00"
def video(i,views=100,channel="UC-peer",duration="PT30S",title=None):
    return {"video_id":f"vid{i:08d}","title":title or f"Topic video {i}","channel_id":channel,"channel_title":f"Channel {channel}","published_at":NOW,"duration":duration,"view_count":views,"like_count":10,"comment_count":2,"default_language":"en"}

class Phase7StoreTests(unittest.TestCase):
    def setUp(self):
        h=tempfile.NamedTemporaryFile(suffix='.db',delete=False);self.path=h.name;h.close();self.history=HistoryStore(self.path);self.store=IntelligenceStore(self.history)
    def tearDown(self):
        try:os.remove(self.path)
        except OSError:pass
    def test_phase7_tables_remain_present_in_current_schema(self):
        with self.history._connect() as c:
            names={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
            self.assertEqual(c.execute('pragma user_version').fetchone()[0],CURRENT_SCHEMA_VERSION);self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
        self.assertTrue({'watchlist_channels','watchlist_videos','watchlist_video_snapshots','watchlist_outlier_analyses','demand_research_snapshots'}<=names)
    def test_v4_to_v5_backup_preserves_idea(self):
        new=['demand_research_snapshots','watchlist_outlier_analyses','watchlist_video_snapshots','watchlist_videos','watchlist_channel_snapshots','watchlist_channels']
        with sqlite3.connect(self.path) as c:
            for table in new:c.execute(f'drop table {table}')
            c.execute('delete from schema_migrations where version=5');c.execute('pragma user_version=4');c.execute("insert into content_ideas(topic,status,created_at,updated_at) values('keep','idea','x','x')")
        result=prepare_database(self.path);self.assertEqual((result.old_version,result.new_version),(4,CURRENT_SCHEMA_VERSION));self.assertTrue(Path(result.backup_path).exists())
        with sqlite3.connect(self.path) as c:self.assertEqual(c.execute('select topic from content_ideas').fetchone()[0],'keep');self.assertEqual(c.execute('pragma foreign_key_check').fetchall(),[])
        Path(result.backup_path).unlink(missing_ok=True)
    def test_channel_creation_duplicate_archive_restore(self):
        c=self.store.create_channel({'channel_id':'UC-one','title':'One','subscriber_count':'12','video_count':'6'},'note')
        with self.assertRaisesRegex(ValueError,'already'):self.store.create_channel({'channel_id':'UC-one','title':'One'})
        self.assertEqual(self.store.update_channel(c['id'],{'state':'archived'})['state'],'archived');self.assertEqual(self.store.update_channel(c['id'],{'state':'active'})['state'],'active')
    def test_channel_refresh_creates_immutable_snapshots_and_recent_videos(self):
        c=self.store.create_channel({'channel_id':'UC-peer','title':'Peer'})
        self.store.snapshot_channel(c['id'],{'channel_id':'UC-peer','title':'Peer','subscriber_count':10,'video_count':6},[video(i,i*100) for i in range(6)])
        updated=self.store.snapshot_channel(c['id'],{'channel_id':'UC-peer','title':'Peer','subscriber_count':11,'video_count':6},[video(i,i*110) for i in range(6)])
        self.assertEqual(len(updated['snapshots']),2);self.assertEqual(len(self.store.videos()),6);self.assertEqual(len(self.store.video(1)['snapshots']),2)
    def test_video_creation_duplicate_and_provenance(self):
        v=self.store.create_video(video(1),'creator note');self.assertEqual(v['source'],'public_observation');self.assertEqual(v['notes'],'creator note');self.assertEqual(v['format'],'youtube_shorts')
        with self.assertRaisesRegex(ValueError,'already'):self.store.create_video(video(1))
    def test_sparse_outlier_returns_no_score(self):
        v=self.store.upsert_video(video(1,1000),snapshot=True);result=self.store.analyze_outlier(v['id'])
        self.assertEqual(result['status'],'insufficient_evidence');self.assertIsNone(result['relative_multiplier']);self.assertIn('at least 5',result['explanation'])
    def test_valid_outlier_uses_median_of_five_peers(self):
        target=self.store.upsert_video(video(99,1000),snapshot=True)
        for i,value in enumerate([100,110,120,130,140]):self.store.upsert_video(video(i,value),snapshot=True)
        result=self.store.analyze_outlier(target['id']);self.assertEqual(result['status'],'possible_outlier');self.assertEqual(result['baseline_median_views'],120);self.assertEqual(result['sample_size'],5);self.assertGreater(result['relative_multiplier'],8);self.assertIn('observational',result['explanation'])
    def test_non_outlier_and_explanation_reject_causation(self):
        target=self.store.upsert_video(video(99,130),snapshot=True)
        for i,value in enumerate([100,110,120,130,140]):self.store.upsert_video(video(i,value),snapshot=True)
        result=self.store.analyze_outlier(target['id']);self.assertEqual(result['status'],'observed_normal');self.assertIn('does not establish',result['signals']['limitation'])
    def test_duration_parser(self):
        self.assertEqual(duration_seconds('PT1M30S'),90);self.assertIsNone(duration_seconds('unknown'))
    def test_demand_snapshots_are_immutable(self):
        values={'topic':'camera','language':'en'};a=self.store.save_demand(values,'insufficient_evidence',{'x':1});b=self.store.save_demand(values,'emerging_signal',{'x':2});self.assertNotEqual(a['id'],b['id']);self.assertEqual(self.store.demands()['total'],2)
    def test_idea_demand_fingerprint_detects_stale_content(self):
        idea=self.history.create_content_idea({'topic':'camera'});fp=idea_fingerprint(idea);saved=self.store.save_demand({'idea_id':idea['id'],'topic':'camera'},'insufficient_evidence',{},fp);self.assertEqual(saved['idea_fingerprint'],fp)
        current=self.history.content_idea(idea['id']);self.assertFalse(current['latest_demand_research']['stale']);self.history.update_content_idea(idea['id'],{'topic':'different'});self.assertTrue(self.history.content_idea(idea['id'])['latest_demand_research']['stale'])

class Phase7DemandTests(unittest.TestCase):
    def research(self,n,channels=None,views=True):
        channels=channels or max(1,n);return {'youtube_results':[{'video_id':str(i),'title':f'camera topic {i}','channel_id':f'c{i%channels}','published_at':NOW,'view_count':100+i if views else None,'like_count':5,'comment_count':1} for i in range(n)]}
    def test_insufficient_classification(self):
        status,e=analyze_demand('camera',self.research(2),[],{});self.assertEqual(status,'insufficient_evidence');self.assertEqual(e['signals'][0]['observed'],2)
    def test_emerging_classification(self):
        self.assertEqual(analyze_demand('camera',self.research(3,2),[],{})[0],'emerging_signal')
    def test_active_classification(self):
        self.assertEqual(analyze_demand('camera',self.research(5,3),[],{})[0],'active_topic')
    def test_strong_observed_interest_with_watchlist_outlier(self):
        watch=[{'id':1,'video_id':'w','title':'best camera test','outlier':{'status':'possible_outlier','relative_multiplier':3},'latest_snapshot':{'captured_at':NOW}}]
        status,e=analyze_demand('camera',self.research(8,4),watch,{});self.assertEqual(status,'strong_observed_interest');self.assertEqual(e['signals'][4]['observed'],1)
    def test_no_fake_volume_cpc_or_guarantee(self):
        _,e=analyze_demand('camera',self.research(5,3),[],{});text=str(e).lower();self.assertNotIn('monthly_search_volume',text);self.assertNotIn('cpc',e);self.assertIn('no official monthly search-volume',text);self.assertNotIn('guaranteed growth',text)
    def test_every_signal_has_provenance(self):
        _,e=analyze_demand('camera',self.research(5,3),[],{});self.assertTrue(all(signal.get('source') for signal in e['signals']))
    def test_mature_personal_evidence_is_gated(self):
        _,small=analyze_demand('camera',self.research(3,2),[],{'learning_allowed':False,'sample_size':4});_,mature=analyze_demand('camera',self.research(3,2),[],{'learning_allowed':True,'sample_size':5,'confidence_label':'Early signal'})
        self.assertEqual(small['personal_evidence']['status'],'insufficient_evidence');self.assertEqual(mature['personal_evidence']['status'],'post_publish_evidence')

class Phase7ClientApiTests(unittest.TestCase):
    def test_public_client_channel_and_video_resolution(self):
        client=YouTubeClient(['key'],1)
        responses=[{'items':[{'id':'UC1','snippet':{'title':'C','thumbnails':{}},'statistics':{'subscriberCount':'3','videoCount':'2'}}]},{'items':[{'id':'abcdefghijk','snippet':{'title':'V','channelId':'UC1','channelTitle':'C'},'statistics':{'viewCount':'9'},'contentDetails':{'duration':'PT20S'}}]}]
        with patch.object(client,'_request_json',side_effect=responses):self.assertEqual(client.get_channel('UC1')['title'],'C');self.assertEqual(client.get_video('abcdefghijk')['view_count'],'9')
    def test_api_rejects_unresolvable_public_resource(self):
        settings=Settings(database_path=':memory:',youtube_api_key='x')
        with patch.object(routes,'get_settings',return_value=settings),patch.object(routes,'_public_client') as factory:
            factory.return_value.get_channel.return_value=None
            with self.assertRaises(HTTPException) as ctx:routes.create_watch_channel(CreateWatchChannelRequest(channel_id='missing'))
            self.assertEqual(ctx.exception.status_code,400)

if __name__=='__main__':unittest.main()
