classdef RatBerryChannel
    %UNTITLED Summary of this class goes here
    %   Detailed explanation goes here
    
    properties
        conn
        name
        connected
    end
    
    methods
        function self = RatBerryChannel(host, port, name)
            %UNTITLED Construct an instance of this class
            %   Detailed explanation goes here
            self.name = name;
            self.conn = tcpclient(host, port);
            self.connected = true;
        end
        
        function reply = run_command(self, command, varargin)

            %METHOD1 Summary of this method goes here
            %   Detailed explanation goes here
            assert(self.connected, 'not connected')
            if nargin>2
                assert(numel(varargin)==1, 'too many inputs');
                args = varargin{1};
                assert(strcmp(class(args), 'struct'), "invalid input for argument 'args'");
            end
            args.command = command;
            self.conn.write(jsonencode(args));
            reply = jsondecode(char(self.conn.readline()));  
        end
    end
end

