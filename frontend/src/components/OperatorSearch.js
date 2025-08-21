import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardTitle,
  CardBody,
  Form,
  FormGroup,
  TextInput,
  Button,
  Grid,
  GridItem,
  Select,
  SelectOption,
  Spinner,
  Alert,
  Title,
  Text,
  Divider,
  Badge
} from '@patternfly/react-core';
import { SearchIcon, TimesIcon } from '@patternfly/react-icons';

function OperatorSearch({ 
  selectedOperators, 
  onOperatorsChange, 
  selectedCatalogs, 
  selectedVersion 
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [availableOperators, setAvailableOperators] = useState([]);
  const [filteredOperators, setFilteredOperators] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [isChannelSelectOpen, setIsChannelSelectOpen] = useState({});
  const [operatorChannels, setOperatorChannels] = useState({});
  const [operatorLimit, setOperatorLimit] = useState(25);

  // Define fetchOperators function FIRST before any useEffect that uses it
  const fetchOperators = useCallback(async () => {
    if (!selectedVersion || !selectedCatalogs || selectedCatalogs.length === 0) {
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const primaryCatalog = selectedCatalogs[0];
      const response = await fetch(
        `/api/operators/list?catalog=${encodeURIComponent(primaryCatalog)}&version=${encodeURIComponent(selectedVersion)}`
      );
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setAvailableOperators(data.operators || []);
      } else {
        setError(data.message || 'Failed to fetch operators');
        setAvailableOperators([]);
      }
    } catch (err) {
      console.error('Error fetching operators:', err);
      setError('Failed to fetch operators');
      setAvailableOperators([]);
    } finally {
      setIsLoading(false);
    }
  }, [selectedVersion, selectedCatalogs]);

  useEffect(() => {
    if (selectedCatalogs && selectedCatalogs.length > 0 && selectedVersion) {
      fetchOperators();
    }
  }, [selectedCatalogs, selectedVersion, fetchOperators]);

  useEffect(() => {
    let filtered = availableOperators;
    if (searchTerm.trim() !== '') {
      filtered = availableOperators.filter(op => 
        op.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (op.display_name && op.display_name.toLowerCase().includes(searchTerm.toLowerCase()))
      );
    }
    setFilteredOperators(filtered);
  }, [searchTerm, availableOperators]);

  const addOperator = (operator) => {
    const newOperator = {
      name: operator.name,
      display_name: operator.display_name,
      channel: 'stable',
      version: operator.version || 'latest'
    };

    const updatedOperators = [...(selectedOperators || []), newOperator];
    onOperatorsChange(updatedOperators);
  };

  const removeOperator = (operatorName) => {
    const updatedOperators = (selectedOperators || []).filter(op => op.name !== operatorName);
    onOperatorsChange(updatedOperators);
  };

  const isOperatorSelected = (operatorName) => {
    return (selectedOperators || []).some(op => op.name === operatorName);
  };

  if (!selectedCatalogs || selectedCatalogs.length === 0) {
    return (
      <Card>
        <CardTitle>Operator Search</CardTitle>
        <CardBody>
          <Alert variant="info" title="No catalogs selected">
            Please select one or more operator catalogs to search for operators.
          </Alert>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardTitle>
        <Title headingLevel="h3" size="lg">
          Operator Search
        </Title>
        <Text component="small">
          Search and select operators from {selectedCatalogs.join(', ')} catalog(s)
        </Text>
      </CardTitle>
      <CardBody>
        <Form>
          <FormGroup label="Search Operators" fieldId="operator-search">
            <TextInput
              type="text"
              id="operator-search"
              value={searchTerm}
              onChange={(event, value) => setSearchTerm(value)}
              placeholder="Search operators by name..."
            />
          </FormGroup>

          {error && (
            <Alert variant="danger" title="Error loading operators">
              {error}
              <div style={{ marginTop: '8px' }}>
                <Button variant="link" onClick={fetchOperators}>
                  Retry
                </Button>
              </div>
            </Alert>
          )}

          {isLoading && (
            <div style={{ textAlign: 'center', margin: '16px 0' }}>
              <Spinner size="lg" />
              <div style={{ marginTop: '8px' }}>Loading operators...</div>
            </div>
          )}

          {!isLoading && filteredOperators.length === 0 && !error && (
            <Alert variant="info" title="No operators found">
              {availableOperators.length === 0 
                ? "No operators available in the selected catalog(s)."
                : searchTerm 
                  ? `No operators match "${searchTerm}". Try a different search term.`
                  : "No operators to display."
              }
            </Alert>
          )}

          {!isLoading && filteredOperators.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                <Title headingLevel="h4" size="md" style={{ marginBottom: 0, marginRight: '16px' }}>
                  Available Operators ({filteredOperators.length > operatorLimit ? operatorLimit : filteredOperators.length}{filteredOperators.length > operatorLimit ? ` of ${filteredOperators.length}` : ''})
                </Title>
                <span style={{ marginLeft: 'auto', fontSize: '0.95em' }}>
                  Show
                  <TextInput
                    type="number"
                    min={1}
                    max={filteredOperators.length}
                    value={operatorLimit}
                    onChange={(e, value) => {
                      let v = parseInt(value, 10);
                      if (isNaN(v) || v < 1) v = 1;
                      if (v > filteredOperators.length) v = filteredOperators.length;
                      setOperatorLimit(v);
                    }}
                    style={{ width: '60px', display: 'inline-block', margin: '0 8px' }}
                    aria-label="Operator result limit"
                  />
                  operators
                </span>
              </div>
              <Grid hasGutter>
                {filteredOperators.slice(0, operatorLimit).map((operator) => (
                  <GridItem span={12} md={6} lg={4} key={operator.name}>
                    <Card>
                      <CardBody>
                        <Title headingLevel="h5" size="sm">
                          {operator.display_name || operator.name}
                        </Title>
                        <Text component="small" style={{ color: '#6a6e73' }}>
                          {operator.name}
                        </Text>
                        {operator.description && (
                          <Text component="p" style={{ marginTop: '8px', fontSize: '14px' }}>
                            {operator.description.length > 100 
                              ? `${operator.description.substring(0, 100)}...`
                              : operator.description
                            }
                          </Text>
                        )}
                        <div style={{ marginTop: '16px' }}>
                          {!isOperatorSelected(operator.name) ? (
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => addOperator(operator)}
                            >
                              Add Operator
                            </Button>
                          ) : (
                            <Badge>✓ Selected</Badge>
                          )}
                        </div>
                      </CardBody>
                    </Card>
                  </GridItem>
                ))}
              </Grid>
            </div>
          )}

          {selectedOperators && selectedOperators.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <Divider style={{ margin: '16px 0' }} />
              <Title headingLevel="h4" size="md" style={{ marginBottom: '16px' }}>
                Selected Operators ({selectedOperators.length})
              </Title>
              <Grid hasGutter>
                {selectedOperators.map((operator) => (
                  <GridItem span={12} md={6} key={operator.name}>
                    <Card>
                      <CardBody>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div>
                            <Title headingLevel="h6" size="sm">
                              {operator.display_name || operator.name}
                            </Title>
                            <Text component="small" style={{ color: '#6a6e73' }}>
                              {operator.name}
                            </Text>
                          </div>
                          <Button
                            variant="plain"
                            size="sm"
                            onClick={() => removeOperator(operator.name)}
                            aria-label={`Remove ${operator.name}`}
                          >
                            <TimesIcon />
                          </Button>
                        </div>
                        <div style={{ marginTop: '8px' }}>
                          <Text component="small">
                            Channel: {operator.channel || 'stable'}
                          </Text>
                        </div>
                      </CardBody>
                    </Card>
                  </GridItem>
                ))}
              </Grid>
            </div>
          )}
        </Form>
      </CardBody>
    </Card>
  );
}

export default OperatorSearch;
