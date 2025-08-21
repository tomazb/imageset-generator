import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Page,
  PageSection,
  Title,
  Text,
  TextContent,
  Tabs,
  Tab,
  TabTitleText,
  PageSectionVariants,
  Alert,
  AlertGroup,
  AlertActionCloseButton,
  Button
} from '@patternfly/react-core';
import SyncAltIcon from '@patternfly/react-icons/dist/esm/icons/sync-alt-icon';
import '@patternfly/patternfly/patternfly.css';
import BasicConfig from './components/BasicConfig';
import AdvancedConfig from './components/AdvancedConfig';
import PreviewGenerate from './components/PreviewGenerate';
import StatusBar from './components/StatusBar';

const API_BASE = '';

function App() {
  console.log('App component is initializing...');
  
  const [activeTab, setActiveTab] = useState(0);
  const [config, setConfig] = useState({
    ocp_versions: [],
    ocp_channel: 'stable-4.14',
    ocp_min_version: '',
    ocp_max_version: '',
    operators: [],
    operator_catalogs: [],
    additional_images: [],
    helm_charts: [],
    output_file: 'imageset-config.yaml',
    kubevirt_container: false
  });
  const [yamlPreview, setYamlPreview] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState('Ready');
  const [alertMessage, setAlertMessage] = useState('');
  const [alertVariant, setAlertVariant] = useState('info');
  const [operatorMappings, setOperatorMappings] = useState({});
  const [ocpReleases, setOcpReleases] = useState([]);
  const [ocpChannels, setOcpChannels] = useState([]);
  const [channelReleases, setChannelReleases] = useState([]);
  const [isLoadingReleases, setIsLoadingReleases] = useState(false);
  const [isLoadingChannels, setIsLoadingChannels] = useState(false);
  const [isLoadingChannelReleases, setIsLoadingChannelReleases] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState('');

  const updateConfig = (updates) => {
    setConfig(prev => ({ ...prev, ...updates }));
  };

  const fetchReleasesForChannelAndVersion = async (channel) => {
    // Extract the version from the current channel (e.g., "stable-4.14" → "4.14")
    const version = channel.split('-')[1] || config.ocp_channel.split('-')[1];
    console.log(`Fetching releases for channel: ${channel}, version: ${version}`);

    if (!channel || !version) return;
    setIsLoadingChannelReleases(true);
    try {
      const response = await axios.get(`${API_BASE}/api/releases/${version}/${channel}`);
      if (response.data.status === 'success') {
        console.log(`Releases for ${channel}:`, response.data.releases);
        setChannelReleases(response.data.releases);
      } else {
        console.error('Failed to fetch releases:', response.data.message);
        setChannelReleases([]);
      }
    } catch (error) {
      console.error('Failed to load releases:', error);
      setChannelReleases([]);
    } finally {
      setIsLoadingChannelReleases(false);
    }
  };
  
  const fetchChannelsForVersion = async (version) => {
    if (!version) return;
    setIsLoadingChannels(true);
    try {
      const response = await axios.get(`${API_BASE}/api/channels/${version}`);
      if (response.data.status === 'success') {
        setOcpChannels(response.data.channels);
      }
    } catch (error) {
      console.error('Failed to load channels:', error);
      setOcpChannels([`stable-${version}`, `fast-${version}`, `candidate-${version}`]);
    } finally {
      setIsLoadingChannels(false);
    }
  };

  const generatePreview = async () => {
    setIsGenerating(true);
    setStatus('Generating preview...');
    setAlertMessage('');
    
    try {
      const response = await axios.post(`${API_BASE}/api/generate/preview`, config);
      setYamlPreview(response.data.yaml);
      setStatus('Preview generated successfully');
      setAlertMessage('YAML preview generated successfully');
      setAlertVariant('success');
    } catch (error) {
      console.error('Failed to generate preview:', error);
      const errorMsg = 'Error generating preview: ' + (error.response?.data?.error || error.message);
      setStatus(errorMsg);
      setAlertMessage(errorMsg);
      setAlertVariant('danger');
      setYamlPreview('');
    } finally {
      setIsGenerating(false);
    }
  };

  const downloadConfig = async () => {
    try {
      setStatus('Generating configuration file...');
      setAlertMessage('');
      const response = await axios.post(`${API_BASE}/api/generate/download`, config, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = config.output_file || 'imageset-config.yaml';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      setStatus('Configuration file downloaded successfully');
      setAlertMessage('Configuration file downloaded successfully');
      setAlertVariant('success');
    } catch (error) {
      console.error('Failed to download config:', error);
      const errorMsg = 'Error downloading configuration: ' + (error.response?.data?.error || error.message);
      setStatus(errorMsg);
      setAlertMessage(errorMsg);
      setAlertVariant('danger');
    }
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    setRefreshStatus('Refreshing all static data...');
    try {
      const resp = await axios.post('/api/refresh/all');
      setRefreshStatus(resp.data.message || 'Refresh complete!');
    } catch (err) {
      setRefreshStatus('Refresh failed: ' + (err.response?.data?.error || err.message));
    }
    setIsRefreshing(false);
  };

  useEffect(() => {
    const loadData = async () => {
      setIsLoadingReleases(true);
      try {
        const [mappingsResponse, releasesResponse] = await Promise.all([
          axios.get(`${API_BASE}/api/operators/mappings`),
          axios.get(`${API_BASE}/api/versions`)
        ]);
        setOperatorMappings(mappingsResponse.data.mappings);
        if (releasesResponse.data.status === 'success') {
          // Ensure releases is always an array
          const releases = Array.isArray(releasesResponse.data.releases) ? releasesResponse.data.releases : [];
          setOcpReleases(releases);
        }
      } catch (error) {
        console.error('Failed to load data:', error);
        setOcpReleases(['4.14', '4.15', '4.16', '4.17', '4.18']);
      } finally {
        setIsLoadingReleases(false);
      }
    };
    loadData();
  }, []);

  return (
    <Page>
      <PageSection variant={PageSectionVariants.darker}>
        <TextContent>
          <Title headingLevel="h1" size="2xl">
            OpenShift ImageSetConfiguration Generator
          </Title>
          <Text>
            Generate ImageSetConfiguration files for OpenShift disconnected installations
          </Text>
        </TextContent>
      </PageSection>

      {alertMessage && (
        <PageSection>
          <AlertGroup>
            <Alert
              variant={alertVariant}
              title={alertMessage}
              actionClose={
                <AlertActionCloseButton onClose={() => setAlertMessage('')} />
              }
            />
          </AlertGroup>
        </PageSection>
      )}

      <PageSection>
        <Button
          variant="secondary"
          icon={<SyncAltIcon />}
          isLoading={isRefreshing}
          isDisabled={isRefreshing}
          onClick={handleRefreshAll}
          style={{ marginBottom: '1rem' }}
        >
          Refresh All Data
        </Button>
        {refreshStatus && <div style={{ marginBottom: '1rem' }}>{refreshStatus}</div>}
      </PageSection>

      <PageSection>
        <Tabs
          activeKey={activeTab}
          onSelect={(event, tabIndex) => setActiveTab(tabIndex)}
        >
          <Tab eventKey={0} title={<TabTitleText>Basic Configuration</TabTitleText>}>
            <BasicConfig
              config={config}
              updateConfig={updateConfig}
              operatorMappings={operatorMappings}
              ocpReleases={ocpReleases}
              ocpChannels={ocpChannels}
              channelReleases={channelReleases}
              onVersionChange={fetchChannelsForVersion}
              onChannelChange={fetchReleasesForChannelAndVersion}
              isLoadingReleases={isLoadingReleases}
              isLoadingChannels={isLoadingChannels}
              isLoadingChannelReleases={isLoadingChannelReleases}
            />
          </Tab>

          <Tab eventKey={1} title={<TabTitleText>Advanced Configuration</TabTitleText>}>
            <AdvancedConfig
              config={config}
              updateConfig={updateConfig}
            />
          </Tab>

          <Tab eventKey={2} title={<TabTitleText>Preview & Generate</TabTitleText>}>
            <PreviewGenerate
              config={config}
              yamlPreview={yamlPreview}
              isGenerating={isGenerating}
              onGeneratePreview={generatePreview}
              onDownloadConfig={downloadConfig}
            />
          </Tab>
        </Tabs>
      </PageSection>

      <StatusBar status={status} />
    </Page>
  );
}

export default App;
